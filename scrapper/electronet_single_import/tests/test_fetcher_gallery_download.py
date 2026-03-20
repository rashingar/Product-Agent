from pathlib import Path

from electronet_single_import.fetcher import ElectronetFetcher
from electronet_single_import.models import GalleryImage


class StubFetcher(ElectronetFetcher):
    def fetch_binary(self, url: str) -> tuple[bytes, str]:
        return b"binary-image", "image/jpeg"



def test_gallery_images_saved_in_model_folder_with_business_names(tmp_path: Path) -> None:
    fetcher = StubFetcher()
    images = [
        GalleryImage(url="https://www.electronet.gr/image/one.jpg", alt="one", position=1),
        GalleryImage(url="https://www.electronet.gr/image/two.jpg", alt="two", position=2),
    ]

    downloaded, warnings, files_written = fetcher.download_gallery_images(
        images=images,
        model="234385",
        output_dir=tmp_path / "234385",
        requested_photos=2,
    )

    assert warnings == []
    assert [item.local_filename for item in downloaded] == ["234385-1.jpg", "234385-2.jpg"]
    assert all((tmp_path / "234385" / "gallery" / name).exists() for name in ["234385-1.jpg", "234385-2.jpg"])
    assert files_written == [
        str(tmp_path / "234385" / "gallery" / "234385-1.jpg"),
        str(tmp_path / "234385" / "gallery" / "234385-2.jpg"),
    ]


def test_besco_images_saved_in_bescos_subfolder_with_section_names(tmp_path: Path) -> None:
    fetcher = StubFetcher()
    images = [
        GalleryImage(url="https://www.electronet.gr/image/one.jpg", alt="one", position=1),
        GalleryImage(url="https://www.electronet.gr/image/three.jpg", alt="three", position=3),
    ]

    downloaded, warnings, files_written = fetcher.download_besco_images(
        images=images,
        output_dir=tmp_path / "234385",
        requested_sections=3,
    )

    assert warnings == ["besco_images_less_than_requested_sections"]
    assert [item.local_filename for item in downloaded] == ["besco1.jpg", "besco3.jpg"]
    assert all((tmp_path / "234385" / "bescos" / name).exists() for name in ["besco1.jpg", "besco3.jpg"])
    assert files_written == [
        str(tmp_path / "234385" / "bescos" / "besco1.jpg"),
        str(tmp_path / "234385" / "bescos" / "besco3.jpg"),
    ]
