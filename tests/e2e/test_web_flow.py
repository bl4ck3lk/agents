"""E2E tests for web application file processing flow."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agents.api.utils.file_parser import parse_file_metadata


class TestFileMetadataDetection:
    """Test file metadata detection."""

    @pytest.fixture
    def sample_csv_content(self) -> str:
        return "id,name,description\n1,Widget,A small widget\n2,Gadget,A cool gadget\n"

    @pytest.fixture
    def sample_json_content(self) -> str:
        return '[{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}]'

    @pytest.fixture
    def sample_jsonl_content(self) -> str:
        return '{"id": 1, "text": "Hello"}\n{"id": 2, "text": "World"}\n'

    @pytest.mark.asyncio
    async def test_parse_csv_metadata(self, tmp_path: Path, sample_csv_content: str):
        """Test parsing CSV file metadata."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(sample_csv_content)

        # Mock storage client
        mock_storage = AsyncMock()
        mock_storage.download_file_to_path = AsyncMock(
            side_effect=lambda key, path: Path(path).write_text(sample_csv_content)
        )

        metadata = await parse_file_metadata("uploads/user/test.csv", mock_storage)

        assert metadata.row_count == 2
        assert metadata.columns == ["id", "name", "description"]
        assert metadata.file_type == "csv"
        assert len(metadata.preview_rows) == 2
        assert metadata.preview_rows[0]["id"] == "1"
        assert metadata.preview_rows[0]["name"] == "Widget"

    @pytest.mark.asyncio
    async def test_parse_json_metadata(self, tmp_path: Path, sample_json_content: str):
        """Test parsing JSON file metadata."""
        json_file = tmp_path / "test.json"
        json_file.write_text(sample_json_content)

        mock_storage = AsyncMock()
        mock_storage.download_file_to_path = AsyncMock(
            side_effect=lambda key, path: Path(path).write_text(sample_json_content)
        )

        metadata = await parse_file_metadata("uploads/user/test.json", mock_storage)

        assert metadata.row_count == 2
        assert metadata.columns == ["id", "text"]
        assert metadata.file_type == "json"
        assert len(metadata.preview_rows) == 2
        assert metadata.preview_rows[0]["id"] == 1
        assert metadata.preview_rows[0]["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_parse_jsonl_metadata(self, tmp_path: Path, sample_jsonl_content: str):
        """Test parsing JSONL file metadata."""
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(sample_jsonl_content)

        mock_storage = AsyncMock()
        mock_storage.download_file_to_path = AsyncMock(
            side_effect=lambda key, path: Path(path).write_text(sample_jsonl_content)
        )

        metadata = await parse_file_metadata("uploads/user/test.jsonl", mock_storage)

        assert metadata.row_count == 2
        assert metadata.columns == ["id", "text"]
        assert metadata.file_type == "jsonl"
        assert len(metadata.preview_rows) == 2

    @pytest.mark.asyncio
    async def test_preview_limit(self, tmp_path: Path):
        """Test that preview is limited to specified rows."""
        # Create CSV with 10 rows
        content = "id,name\n" + "\n".join([f"{i},Item{i}" for i in range(10)])
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(content)

        mock_storage = AsyncMock()
        mock_storage.download_file_to_path = AsyncMock(
            side_effect=lambda key, path: Path(path).write_text(content)
        )

        metadata = await parse_file_metadata("uploads/user/test.csv", mock_storage, preview_limit=3)

        assert metadata.row_count == 10
        assert len(metadata.preview_rows) == 3


class TestOutputFormatting:
    """Test output format options."""

    def test_format_result_enriched(self):
        """Test enriched output format includes original + AI data."""
        from agents.processing_service.processor import format_result

        original = {"id": 1, "text": "Hello", "_idx": 0}
        result = {"id": 1, "text": "Hello", "_idx": 0, "translation": "Hola"}

        formatted = format_result(result, original, "enriched")

        assert formatted["id"] == 1
        assert formatted["text"] == "Hello"
        assert formatted["translation"] == "Hola"
        assert formatted["_idx"] == 0

    def test_format_result_separate(self):
        """Test separate output format includes only AI data."""
        from agents.processing_service.processor import format_result

        original = {"id": 1, "text": "Hello", "_idx": 0}
        result = {"id": 1, "text": "Hello", "_idx": 0, "translation": "Hola"}

        formatted = format_result(result, original, "separate")

        assert "text" not in formatted  # Original text excluded
        assert formatted["translation"] == "Hola"
        assert formatted["_idx"] == 0

    def test_format_result_with_schema(self):
        """Test output schema filters fields."""
        from agents.processing_service.processor import format_result

        original = {"id": 1, "text": "Hello", "_idx": 0}
        result = {
            "id": 1,
            "text": "Hello",
            "_idx": 0,
            "translation": "Hola",
            "confidence": 0.95,
            "extra": "ignored",
        }

        formatted = format_result(
            result, original, "enriched", output_schema={"translation": "string"}
        )

        assert formatted["translation"] == "Hola"
        assert "extra" not in formatted


class TestTaskQClient:
    """Test TaskQ client functionality."""

    @pytest.mark.asyncio
    async def test_enqueue_task_queue_not_found(self):
        """Test error when queue doesn't exist."""
        from unittest.mock import MagicMock

        from agents.taskq.client import enqueue_task

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Queue 'llm_processing' not found"):
            await enqueue_task(mock_session, {"test": "payload"})

    @pytest.mark.asyncio
    async def test_enqueue_task_success(self):
        """Test successful task enqueueing."""
        import uuid
        from unittest.mock import MagicMock

        from agents.taskq.client import enqueue_task

        mock_session = AsyncMock()

        # First call returns queue ID
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (str(uuid.uuid4()),)
        mock_session.execute.return_value = mock_result

        task_id = await enqueue_task(
            mock_session,
            {"web_job_id": "job_123", "prompt": "Test prompt"},
            idempotency_key="job_123",
        )

        assert task_id is not None
        assert mock_session.execute.call_count == 2  # get_queue_id + insert
