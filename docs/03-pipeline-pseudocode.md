# 03 — Pseudo code: Cách xây dựng từng pipeline

> Tư duy: Biết **làm gì** (blackbox) → biết **tại sao** (architecture) → giờ hiểu **làm như thế nào** (implementation).
> Mỗi pipeline được mô tả bằng pseudo code dễ hiểu, sau đó liên kết với code thực.

---

## Pipeline 1: Crawl một bài Wikipedia

### Bài toán
```
INPUT:  tiêu đề bài viết (vd: "Machine learning") + ngôn ngữ (vd: "en")
OUTPUT: { title, url, text } hoặc null nếu không tìm thấy
```

### Pseudo code
```
FUNCTION fetch_page(title, lang):
  api_url = "https://{lang}.wikipedia.org/w/api.php"
  
  FOR attempt in [1, 2, 3]:
    TRY:
      response = HTTP_GET(api_url, params={
        action: "query",
        titles: title,
        prop: "extracts",       // lấy full text
        explaintext: True,      // plain text, không HTML
        inprop: "url",          // lấy URL
        redirects: True,        // theo redirect
      })
      
      page = response.json["query"]["pages"][first_key]
      
      IF "missing" in page:
        RETURN null             // bài không tồn tại
      
      RETURN {
        title: page["title"],
        url:   page["fullurl"],
        text:  page["extract"],
        lang:  lang,
      }
    
    EXCEPT network_error:
      sleep(2 * attempt)        // exponential backoff: 2s, 4s, 6s
  
  RAISE "Failed after 3 retries"
```

### Code thực tương ứng
→ `src/utils/crawler.py` — method `fetch_page()`

---

## Pipeline 2: Crawl song song nhiều bài

### Bài toán
```
INPUT:  danh sách titles, concurrency=3
OUTPUT: (danh sách pages thành công, danh sách lỗi)
```

### Pseudo code
```
FUNCTION fetch_pages_parallel(titles, concurrency=3):
  semaphore = Semaphore(concurrency)   // max 3 request cùng lúc
  
  ASYNC_FUNCTION fetch_one(title):
    ACQUIRE semaphore                  // nếu đã có 3 request → đợi
    result = await fetch_page(title)
    sleep(rate_limit / concurrency)    // tôn trọng Wikipedia rate limit
    RELEASE semaphore
    RETURN result
  
  // Tạo tất cả tasks đồng thời
  tasks = [fetch_one(title) for title in titles]
  
  // Chạy song song, thu kết quả
  results = await GATHER_ALL(tasks, return_exceptions=True)
  
  pages  = [r for r in results if r is not Exception and r.text]
  errors = [{"title": t, "error": str(r)} 
            for t, r in zip(titles, results) 
            if r is Exception]
  
  RETURN pages, errors
```

**Tại sao Semaphore tốt hơn asyncio.sleep()?**
```
Không có Semaphore:
  t=0: Gửi 100 request cùng lúc → Wikipedia block IP

Có Semaphore(3):
  t=0: Gửi request 1, 2, 3
  t=2: Request 1 xong → gửi request 4
  t=2: Request 2 xong → gửi request 5
  ...→ luôn chỉ có tối đa 3 request đang chờ
```

### Code thực tương ứng
→ `src/utils/crawler.py` — method `fetch_pages_parallel()`

---

## Pipeline 3: RAG Indexing (Clean → Chunk → Embed → Index)

### Bài toán
```
INPUT:  danh sách Article objects từ PostgreSQL (is_indexed=False)
OUTPUT: số articles đã xử lý, số chunks đã index vào ES
```

### Pseudo code
```
FUNCTION run_indexing(articles, batch_size=100):
  ensure_es_index_exists()    // tạo index nếu chưa có
  
  all_bulk_docs = []          // gom tất cả docs trước khi bulk insert
  processed_ids = []
  
  FOR article in articles:
    
    // BƯỚC 1: CLEAN
    clean_text = clean_wikipedia_markup(article.raw_text)
    IF clean_text is empty:
      mark_as_indexed(article.id)    // bài rỗng, bỏ qua
      CONTINUE
    
    // BƯỚC 2: CHUNK
    chunks = split_into_chunks(
      text=clean_text,
      chunk_size=500,          // ~400 từ per chunk
      overlap=50               // 50 ký tự overlap để giữ ngữ cảnh
    )
    IF chunks is empty:
      mark_as_indexed(article.id)
      CONTINUE
    
    // BƯỚC 3: EMBED (batch — nhanh hơn từng cái)
    embeddings = model.encode(chunks)   // trả về matrix [n_chunks × 384]
    
    // BƯỚC 4: Chuẩn bị bulk documents
    FOR i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
      all_bulk_docs.append({
        "text":        chunk,
        "embedding":   embedding,     // [384 floats]
        "title":       article.title,
        "url":         article.url,
        "chunk_index": i,
        "lang":        article.lang,
      })
    
    processed_ids.append(article.id)
  
  // BƯỚC 5: BULK INDEX (1 round-trip thay vì N)
  IF all_bulk_docs:
    es.helpers.bulk(es_client, all_bulk_docs)
  
  // BƯỚC 6: Đánh dấu đã xử lý
  FOR id in processed_ids:
    mark_as_indexed(id)
  
  RETURN { processed: len(processed_ids), indexed: len(all_bulk_docs) }
```

### Code thực tương ứng
→ `src/services/index_service.py` — method `run_background()`
→ `src/utils/cleaner.py` — `clean_text()`
→ `src/utils/chunker.py` — `chunk_data()`
→ `src/utils/embedder.py` — `get_embeddings_batch()`
→ `src/core/vector_db.py` — `bulk_index_documents()`

---

## Pipeline 4: Background Job (không block API)

### Bài toán
```
Indexing có thể mất 5-15 phút.
HTTP timeout sau 30 giây.
→ Cần cơ chế "submit và poll".
```

### Pseudo code
```
// API Handler (trả về ngay)
FUNCTION POST /index/run(batch_size):
  job = JobStore.create(type="index_run", params={batch_size})
  
  thread = new Thread(target=run_indexing_background, args=[job])
  thread.start()               // chạy nền, không block
  
  RETURN { job_id: job.id, status: "pending" }   // trả về ngay <1ms


// Background thread (chạy song song)
FUNCTION run_indexing_background(job):
  job.status = "running"
  job.started_at = now()
  
  db = new_database_session()  // session riêng, không share với request
  
  TRY:
    total = count_unindexed_articles(db)
    
    WHILE True:
      articles = get_unindexed(db, limit=batch_size)
      IF articles is empty: BREAK
      
      run_batch(articles)
      
      // Cập nhật progress để client poll được
      job.progress = {
        articles_processed: ...,
        chunks_indexed: ...,
        percent: processed / total * 100,
      }
    
    job.status = "done"
    job.result = { ... }
  
  EXCEPT error:
    job.status = "failed"
    job.error = str(error)
  
  FINALLY:
    db.close()


// Poll endpoint
FUNCTION GET /index/status/{job_id}:
  job = JobStore.get(job_id)
  IF not job: RETURN 404
  RETURN job.to_dict()         // trả về trạng thái hiện tại
```

### Code thực tương ứng
→ `src/core/job_store.py` — `Job`, `JobStore`
→ `src/services/index_service.py` — `run_background()`
→ `src/controller/index_controller.py` — `run()`, `get_job_status()`

---

## Pipeline 5: Hybrid Search + RRF

### Bài toán
```
INPUT:  query text, top_k=5
OUTPUT: danh sách chunks liên quan nhất, sắp xếp theo RRF score
```

### Pseudo code
```
FUNCTION hybrid_search(query, top_k=5):
  pool = 20   // số candidates từ mỗi phương pháp
  k_rrf = 60  // hằng số RRF
  
  // BƯỚC 1: BM25 search (từ khoá)
  bm25_hits = es.search(
    query={ "multi_match": { "query": query, "fields": ["text", "title"] } },
    size=pool
  )
  // bm25_hits = [doc_A, doc_B, doc_C, ...] sắp xếp theo BM25 score
  
  // BƯỚC 2: Embed query → vector search
  query_vector = embedding_model.encode(query)
  vector_hits = es.search(
    knn={ "field": "embedding", "query_vector": query_vector, "k": pool },
    size=pool
  )
  // vector_hits = [doc_A, doc_D, doc_B, ...] sắp xếp theo cosine similarity
  
  // BƯỚC 3: RRF Fusion
  scores = {}
  sources = {}
  
  FOR rank, doc in enumerate(bm25_hits):
    scores[doc.id] = scores.get(doc.id, 0) + 1 / (k_rrf + rank + 1)
    sources[doc.id] = doc.source
  
  FOR rank, doc in enumerate(vector_hits):
    scores[doc.id] = scores.get(doc.id, 0) + 1 / (k_rrf + rank + 1)
    sources[doc.id] = doc.source
  
  // BƯỚC 4: Sort và lấy top-K
  sorted_ids = sort(scores, by=score, descending=True)[:top_k]
  
  RETURN [
    { id, score: scores[id], text, title, url, chunk_index }
    for id in sorted_ids
  ]
```

### Code thực tương ứng
→ `src/core/vector_db.py` — `hybrid_search()`

---

## Pipeline 6: RAG Answer (Retrieval-Augmented Generation)

### Bài toán
```
INPUT:  câu hỏi tự nhiên
OUTPUT: câu trả lời + nguồn trích dẫn
```

### Pseudo code
```
FUNCTION answer_query(question):
  
  // BƯỚC 1: Retrieve top chunks
  chunks = hybrid_search(question, top_k=RAG_HYBRID_POOL)  // mặc định 10
  
  IF chunks is empty:
    RETURN { answer: "Không tìm thấy thông tin", sources: [] }
  
  // BƯỚC 2: Rerank (đơn giản theo RRF score, lấy top-N)
  top_chunks = sort(chunks, by=score)[:RAG_TOP_K_CONTEXT]  // mặc định 3
  
  // BƯỚC 3: Build context string
  context = ""
  FOR i, chunk in enumerate(top_chunks):
    context += f"[{i+1}] {chunk.title}\n{chunk.text}\n\n"
  
  // BƯỚC 4: Build prompt
  prompt = f"""
    Use the following Wikipedia context to answer the question.
    
    --- CONTEXT ---
    {context}
    --- END CONTEXT ---
    
    Question: {question}
    Answer:
  """
  
  // BƯỚC 5: LLM generation
  answer = openai.chat(
    model="gpt-4o-mini",
    system="You are an assistant answering based on Wikipedia context...",
    user=prompt
  )
  
  RETURN { answer: answer, sources: top_chunks }
```

### Code thực tương ứng
→ `src/services/search_service.py` — `answer_query()`
→ `src/core/llm_client.py` — `generate_response()`

---

## Tổng hợp: Tất cả pipelines và dependencies

```
WikiCrawler.fetch_page()
    └─► CrawlService.fetch_and_save()
            └─► ArticleRepository.save()
                    └─► PostgreSQL

IndexService.run_background()
    ├─► ArticleRepository.get_unindexed()  ← PostgreSQL
    ├─► TextCleaner.clean_text()
    ├─► TextChunker.chunk_data()
    ├─► Embedder.get_embeddings_batch()    ← SentenceTransformer
    ├─► VectorDB.bulk_index_documents()    ← Elasticsearch
    └─► ArticleRepository.mark_indexed()  ← PostgreSQL

SearchService.answer_query()
    ├─► Embedder.get_embedding()           ← SentenceTransformer
    ├─► VectorDB.hybrid_search()           ← Elasticsearch
    └─► LLMClient.generate_response()      ← OpenAI API
```
