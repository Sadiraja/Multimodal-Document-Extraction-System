def extract_document(*args, **kwargs):
    """Lazy wrapper so importing the package does not pull in heavy deps."""
    from .pipeline import extract_document as _impl
    return _impl(*args, **kwargs)


__all__ = ["extract_document"]
