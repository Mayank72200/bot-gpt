from sqlalchemy import Engine, text


def migrate_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='document_chunks' LIMIT 1")
        ).first()
        if not table_exists:
            return

        columns = connection.execute(text("PRAGMA table_info(document_chunks)")).fetchall()
        column_names = {str(col[1]) for col in columns}
        if "chunk_text" not in column_names:
            return

        connection.execute(
            text(
                """
                CREATE TABLE document_chunks_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    document_id VARCHAR(36) NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_chunks_new (id, document_id, chunk_index)
                SELECT id, document_id, chunk_index
                FROM document_chunks
                """
            )
        )
        connection.execute(text("DROP TABLE document_chunks"))
        connection.execute(text("ALTER TABLE document_chunks_new RENAME TO document_chunks"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id ON document_chunks (document_id)"))
