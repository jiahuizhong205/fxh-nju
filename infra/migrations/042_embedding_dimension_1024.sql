-- 百炼 text-embedding-v4 不支持 384 维；旧 mock 向量不可与 1024 维真实向量混用。
ALTER TABLE document_chunks
  ALTER COLUMN embedding TYPE vector(1024)
  USING NULL::vector(1024);
