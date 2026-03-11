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

    # LLM provider: "openai" (default, one key for everything) or "anthropic"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""  # only needed if llm_provider=anthropic

    # Embeddings (uses OpenAI regardless of llm_provider)
    embedding_model: str = "text-embedding-3-small"

    # LanceDB vector store (defaults to s3://{B2_BUCKET_NAME}/lancedb/)
    lancedb_uri: str = ""  # override with custom S3 URI or local path

    # Document processing pipeline
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunks_per_doc: int = 500
    chunk_strategy: str = "recursive"  # "recursive" or "semantic"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def lancedb_storage_uri(self) -> str:
        """Resolve LanceDB URI, defaulting to B2 bucket path."""
        if self.lancedb_uri:
            return self.lancedb_uri
        return f"s3://{self.b2_bucket_name}/lancedb/"


settings = Settings()
