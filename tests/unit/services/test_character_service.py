"""Unit tests for CharacterService."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from persona_agent.services.character_service import (
    CharacterService,
    CharacterNotFoundError,
    CharacterLoadError,
)
from persona_agent.config.schemas.character import CharacterProfile


class TestCharacterService:
    """Test suite for CharacterService."""

    @pytest.fixture
    def service(self):
        """Create a CharacterService instance."""
        return CharacterService()

    @pytest.fixture
    def mock_loader(self):
        """Create a mock ConfigLoader."""
        return Mock()

    def test_list_characters(self, service, mock_loader):
        """Test listing characters."""
        # Arrange
        mock_loader.list_characters.return_value = ["default", "companion", "pixel"]
        service._loader = mock_loader

        # Act
        result = service.list_characters()

        # Assert
        assert result == ["default", "companion", "pixel"]
        mock_loader.list_characters.assert_called_once()

    def test_list_characters_empty(self, service, mock_loader):
        """Test listing characters when none exist."""
        # Arrange
        mock_loader.list_characters.return_value = []
        service._loader = mock_loader

        # Act
        result = service.list_characters()

        # Assert
        assert result == []

    def test_get_character_success(self, service, mock_loader):
        """Test getting an existing character."""
        # Arrange
        mock_profile = Mock(spec=CharacterProfile)
        mock_profile.name = "Test Character"
        mock_loader.load_character.return_value = mock_profile
        service._loader = mock_loader

        # Act
        result = service.get_character("default")

        # Assert
        assert result == mock_profile
        mock_loader.load_character.assert_called_once_with("default")

    def test_get_character_not_found(self, service, mock_loader):
        """Test getting a non-existent character raises error."""
        # Arrange
        from persona_agent.utils.exceptions import FileNotFoundError as PAFileNotFoundError

        mock_loader.load_character.side_effect = PAFileNotFoundError("default")
        service._loader = mock_loader

        # Act & Assert
        with pytest.raises(CharacterNotFoundError) as exc_info:
            service.get_character("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.details["character_name"] == "nonexistent"

    def test_character_exists_true(self, service, mock_loader):
        """Test checking if character exists (True case)."""
        # Arrange
        mock_loader.list_characters.return_value = ["default", "companion"]
        service._loader = mock_loader

        # Act
        result = service.character_exists("default")

        # Assert
        assert result is True

    def test_character_exists_false(self, service, mock_loader):
        """Test checking if character exists (False case)."""
        # Arrange
        mock_loader.list_characters.return_value = ["default", "companion"]
        service._loader = mock_loader

        # Act
        result = service.character_exists("nonexistent")

        # Assert
        assert result is False

    def test_clear_cache(self, service, mock_loader):
        """Test clearing the character cache."""
        # Arrange
        service._loader = mock_loader

        # Act
        service.clear_cache()

        # Assert
        mock_loader.clear_cache.assert_called_once()

    def test_load_character_from_path_success(self, service, tmp_path):
        """Test loading character from specific path."""
        # Arrange
        char_file = tmp_path / "test_char.yaml"
        char_file.write_text("name: Test Character")

        with patch.object(CharacterProfile, "from_yaml") as mock_from_yaml:
            mock_profile = Mock(spec=CharacterProfile)
            mock_from_yaml.return_value = mock_profile

            # Act
            result = service.load_character(char_file)

            # Assert
            assert result == mock_profile
            mock_from_yaml.assert_called_once_with(char_file)

    def test_load_character_from_path_not_found(self, service, tmp_path):
        """Test loading character from non-existent path raises error."""
        # Arrange
        char_file = tmp_path / "nonexistent.yaml"

        # Act & Assert
        with pytest.raises(CharacterNotFoundError) as exc_info:
            service.load_character(char_file)

        assert "nonexistent" in str(exc_info.value)

    def test_load_character_yaml_error(self, service, tmp_path):
        """Test loading character with invalid YAML raises error."""
        # Arrange
        char_file = tmp_path / "bad_char.yaml"
        char_file.write_text("invalid: yaml: content: [")

        # Act & Assert
        with pytest.raises(CharacterLoadError) as exc_info:
            service.load_character(char_file)

        assert "bad_char" in str(exc_info.value)
        assert "Invalid YAML" in str(exc_info.value)

    def test_with_config_dir_classmethod(self, tmp_path):
        """Test the with_config_dir factory method."""
        # Act
        service = CharacterService.with_config_dir(tmp_path)

        # Assert
        assert isinstance(service, CharacterService)
        assert service._loader.config_dir == tmp_path

    def test_character_service_error_details(self):
        """Test that CharacterServiceError includes proper details."""
        # Arrange & Act
        error = CharacterNotFoundError("test_char")

        # Assert
        assert error.details["character_name"] == "test_char"
        assert "test_char" in str(error)

    def test_character_load_error_with_reason(self):
        """Test CharacterLoadError includes reason in details."""
        # Arrange & Act
        error = CharacterLoadError("test_char", "File corrupted")

        # Assert
        assert error.details["reason"] == "File corrupted"
        assert "test_char" in str(error)
