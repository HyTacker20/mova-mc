from app.data import load_languages


class TestData:
    def test_load_languages_returns_list(self):
        languages = load_languages()
        assert len(languages) >= 80

    def test_load_languages_has_en_us(self):
        languages = load_languages()
        values = [lang.get("value", "") for lang in languages]
        assert "en_US" in values
