import unittest

from apps.content_planning.utils.ref_image_filter import (
    filter_usable_ref_urls,
    is_usable_ref_url,
)


class IsUsableRefUrlTests(unittest.TestCase):
    def test_accepts_http_https_and_local_path(self) -> None:
        self.assertTrue(is_usable_ref_url("https://sns-img-bd.xhscdn.com/abc.jpg"))
        self.assertTrue(is_usable_ref_url("http://cdn.example.cn/x.png"))
        self.assertTrue(is_usable_ref_url("/static/source_images/a.png"))

    def test_rejects_empty_or_invalid_scheme(self) -> None:
        self.assertFalse(is_usable_ref_url(""))
        self.assertFalse(is_usable_ref_url(None))  # type: ignore[arg-type]
        self.assertFalse(is_usable_ref_url("   "))
        self.assertFalse(is_usable_ref_url("ftp://foo/bar.png"))
        self.assertFalse(is_usable_ref_url("data:image/png;base64,abc"))
        self.assertFalse(is_usable_ref_url("example.com/x.jpg"))

    def test_rejects_known_placeholder_hosts(self) -> None:
        self.assertFalse(is_usable_ref_url("https://example.com/img1.jpg"))
        self.assertFalse(is_usable_ref_url("https://www.example.com/x.png"))
        self.assertFalse(is_usable_ref_url("https://EXAMPLE.org/y.png"))
        self.assertFalse(is_usable_ref_url("https://mock-cdn.example.com/z.png"))


class FilterUsableRefUrlsTests(unittest.TestCase):
    def test_filters_and_dedupes_preserving_order(self) -> None:
        urls = [
            "https://example.com/img1.jpg",
            "https://cdn.real.com/a.png",
            "",
            None,
            "https://cdn.real.com/a.png",  # dup
            "/static/source_images/b.png",
            "ftp://x/x.png",
        ]
        out = filter_usable_ref_urls(urls)  # type: ignore[arg-type]
        self.assertEqual(
            out,
            ["https://cdn.real.com/a.png", "/static/source_images/b.png"],
        )

    def test_empty_input(self) -> None:
        self.assertEqual(filter_usable_ref_urls([]), [])
        self.assertEqual(filter_usable_ref_urls(None), [])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
