class TranslationError(Exception):
    pass


class FileParsingError(TranslationError):
    pass


class JarPackagingError(TranslationError):
    pass


class ConfigurationError(TranslationError):
    pass


class TranslationServiceError(TranslationError):
    pass


class RateLimitExceededError(TranslationServiceError):
    pass
