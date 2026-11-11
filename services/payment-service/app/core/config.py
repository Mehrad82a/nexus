import os
from dataclasses import dataclass, field



@dataclass(frozen=True)
class Settings:
    service_name: str = 'payment-service'
    debug: bool = field(default_factory=lambda: os.environ.get('PAYMENT_DEBUG', 'True').lower() == 'true')

    # PostgreSQL Configuration (nexus_payment_db)
    postgres_user: str = field(default_factory=lambda: os.environ.get('POSTGRES_USER', 'nexus_admin'))
    postgres_password: str = field(default_factory=lambda: os.environ.get('POSTGRES_PASSWORD', 'nexus_pass'))
    postgres_host: str = field(default_factory=lambda: os.environ.get('POSTGRES_HOST', 'postgres'))
    postgres_port: int = field(default_factory=lambda: int(os.environ.get('POSTGRES_PORT', '5432')))
    payment_db_name: str = field(default_factory=lambda: os.environ.get('PAYMENT_DB_NAME', 'nexus_payment_db'))


    # Redis Configuration (Database 3 for Payment Service)
    redis_host: str = field(default_factory=lambda: os.environ.get('REDIS_HOST', 'redis'))
    redis_port: int = field(default_factory=lambda: int(os.environ.get('REDIS_PORT', '6379')))
    redis_password: str = field(default_factory=lambda: os.environ.get('REDIS_PASSWORD', 'redis_pass'))
    redis_db: int = 3


    # Security & Cryptographic Keys
    jwt_secret_key: str = field(default_factory=lambda: os.environ.get('JWT_SECRET_KEY', 'django-insecure-fallback-jwt-key'))
    jwt_algorithm: str = 'HS256'

    webhook_secret: str = field(default_factory=lambda: os.environ.get('PAYMENT_WEBHOOK_SECRET', 'django-insecure-fallback-webhook-key'))



    @property
    def async_database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.payment_db_name}'
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f'postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.payment_db_name}'
        )


settings = Settings()
