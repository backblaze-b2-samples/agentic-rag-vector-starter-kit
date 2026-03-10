from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # B2 storage
    b2_s3_endpoint: str = "https://s3.us-west-004.backblazeb2.com"
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_public_url: str = ""

    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # Upload limits
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # LLM (Anthropic for chat/classification/reranking)
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"

    # Embeddings
    embedding_provider: str = "openai"  # "openai" or "huggingface"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""

    # LanceDB (S3-backed vector store)
    lancedb_uri: str = ""  # e.g. s3://bucket/lancedb/ or local path

    # Document processing pipeline
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunks_per_doc: int = 500

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def lancedb_storage_uri(self) -> str:
        """Resolve LanceDB URI, defaulting to B2 bucket path."""
        if self.lancedb_uri:
            return self.lancedb_uri
        # Default: use B2 bucket with S3-compatible URI
        return (
            f"s3://{self.b2_bucket_name}/lancedb/"
            f"?region=us-west-004"
            f"&endpoint={self.b2_s3_endpoint}"
        )


settings = Settings()
