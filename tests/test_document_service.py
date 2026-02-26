import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BadRequestError
from app.models.document import DocumentChunk
from app.services.document_service import DocumentService


class DummyEmbeddingService:
    async def embed_text(self, text: str) -> np.ndarray:
        return np.zeros(get_settings().vector_dim, dtype=np.float32)


class DummyFaissManager:
    def __init__(self) -> None:
        self.calls = 0

    def add_text_embeddings(self, texts: list[str], embeddings: list[np.ndarray], metadatas: list[dict], ids: list[str]) -> None:
        self.calls += 1
        assert len(texts) == len(embeddings) == len(metadatas) == len(ids)


def _build_service() -> DocumentService:
    settings = get_settings().model_copy(deep=True)
    return DocumentService(
        settings=settings,
        embedding_service=DummyEmbeddingService(),  # type: ignore[arg-type]
        faiss_manager=DummyFaissManager(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_upload_document_persists_chunk_metadata_only(db_session: Session, user_id: str) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.chunk_size_chars = 20
    settings.chunk_overlap_chars = 0

    faiss_manager = DummyFaissManager()
    service = DocumentService(
        settings=settings,
        embedding_service=DummyEmbeddingService(),  # type: ignore[arg-type]
        faiss_manager=faiss_manager,  # type: ignore[arg-type]
    )

    document, chunk_count = await service.upload_document(
        db=db_session,
        user_id=user_id,
        title="doc",
        text="alpha beta gamma delta epsilon zeta eta theta",
    )

    rows = (
        db_session.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    assert chunk_count > 0
    assert len(rows) == chunk_count
    assert [row.chunk_index for row in rows] == list(range(chunk_count))
    assert faiss_manager.calls == 1


def test_extract_text_from_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakePdfReader:
        def __init__(self, *_args, **_kwargs) -> None:
            self.pages = [FakePage("first"), FakePage("second")]

    monkeypatch.setattr("app.services.document_service.PdfReader", FakePdfReader)
    service = _build_service()

    text = service.extract_text_from_uploaded_file("sample.pdf", b"fake-pdf-content")

    assert text == "first\nsecond"


def test_extract_text_from_docx(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeParagraph:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeDocx:
        def __init__(self, *_args, **_kwargs) -> None:
            self.paragraphs = [FakeParagraph("alpha"), FakeParagraph("beta")]

    monkeypatch.setattr("app.services.document_service.DocxDocument", FakeDocx)
    service = _build_service()

    text = service.extract_text_from_uploaded_file("sample.docx", b"fake-docx-content")

    assert text == "alpha\nbeta"


def test_extract_text_from_uploaded_file_unsupported_type() -> None:
    service = _build_service()

    with pytest.raises(BadRequestError) as exc:
        service.extract_text_from_uploaded_file("sample.xlsx", b"dummy")

    assert exc.value.code == "UNSUPPORTED_DOCUMENT_TYPE"
