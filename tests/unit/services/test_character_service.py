"""Unit tests for CharacterService."""

from unittest.mock import Mock, patch

import pytest

from persona_agent.config.schemas.character import CharacterProfile
from persona_agent.services.character_service import (
    CharacterLoadError,
    CharacterNotFoundError,
    CharacterService,
    CharacterServiceError,
)


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

    def test_validate_character_name_valid(self, service):
        """Test that valid character names pass validation."""
        # Arrange, Act & Assert - should not raise
        service._validate_character_name("default")
        service._validate_character_name("my-character")
        service._validate_character_name("companion_v2")

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "../etc/passwd",
            "..\\windows\\system32",
            "config:yaml",
            "char<name>",
            "char/name",
            "char\\name",
            "char*name",
            'char"name',
            "char?name",
            "char|name",
            "",
            "   ",
        ],
    )
    def test_validate_character_name_invalid_raises(self, service, invalid_name):
        """Test that invalid character names raise CharacterServiceError."""
        # Act & Assert
        with pytest.raises(CharacterServiceError) as exc_info:
            service._validate_character_name(invalid_name)

        assert "Invalid character name" in str(exc_info.value)

    def test_create_character_valid(self, service, tmp_path, mock_loader):
        """Test creating a character with a valid name."""
        # Arrange
        mock_loader.config_dir = tmp_path
        service._loader = mock_loader

        profile = Mock(spec=CharacterProfile)
        profile.name = "new_char"
        with patch.object(profile, "to_yaml"):
            # Act
            result = service.create_character(profile)

        # Assert
        assert result == tmp_path / "characters" / "new_char.yaml"
        mock_loader.clear_cache.assert_called_once()

    def test_create_character_invalid_name_raises(self, service):
        """Test creating a character with a path traversal name raises error."""
        # Arrange
        profile = Mock(spec=CharacterProfile)
        profile.name = "../../etc/passwd"

        # Act & Assert
        with pytest.raises(CharacterServiceError) as exc_info:
            service.create_character(profile)

        assert "Invalid character name" in str(exc_info.value)

    def test_update_character_valid(self, service, tmp_path, mock_loader):
        """Test updating a character with a valid name."""
        # Arrange
        mock_loader.config_dir = tmp_path
        service._loader = mock_loader

        profile = Mock(spec=CharacterProfile)
        profile.name = "updated_char"
        with patch.object(profile, "to_yaml"):
            # Act
            result = service.update_character("updated_char", profile)

        # Assert
        assert result == tmp_path / "characters" / "updated_char.yaml"
        mock_loader.clear_cache.assert_called_once()

    def test_update_character_invalid_name_raises(self, service):
        """Test updating a character with a path traversal name raises error."""
        # Arrange
        profile = Mock(spec=CharacterProfile)
        profile.name = "updated_char"

        # Act & Assert
        with pytest.raises(CharacterServiceError) as exc_info:
            service.update_character("../../etc/passwd", profile)

        assert "Invalid character name" in str(exc_info.value)

    def test_save_character_no_arbitrary_path(self, service, tmp_path, mock_loader):
        """Test save_character does not accept arbitrary path parameter."""
        # Arrange
        mock_loader.config_dir = tmp_path
        service._loader = mock_loader

        profile = Mock(spec=CharacterProfile)
        profile.name = "saved_char"
        with patch.object(profile, "to_yaml"):
            # Act
            result = service.save_character(profile)

        # Assert
        assert result == tmp_path / "characters" / "saved_char.yaml"
