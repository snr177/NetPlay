import time
from pathlib import Path

import libtorrent as lt


def _format_progress_bar(progress: float, width: int = 30) -> str:
    progress = min(max(progress, 0.0), 1.0)
    filled = int(progress * width)
    return f"[{'#' * filled}{'-' * (width - filled)}]"


def download_magnet(
    magnet_link: str,
    save_path: str | Path = "./Downloads",
    metadata_timeout: float = 180,
    stall_timeout: float = 300,
) -> Path:
    """Download a magnet link, failing if metadata or data stops arriving."""
    magnet_link = magnet_link.strip()
    if not magnet_link.lower().startswith("magnet:?"):
        raise ValueError("The link must be a magnet URI.")
    if metadata_timeout <= 0 or stall_timeout <= 0:
        raise ValueError("Timeouts must be greater than zero.")

    destination = Path(save_path).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    session = lt.session()
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = str(destination)
    params.storage_mode = lt.storage_mode_t.storage_mode_sparse
    handle = session.add_torrent(params)

    print("Fetching torrent metadata...")
    metadata_started = time.monotonic()
    while True:
        status = handle.status()
        if status.error:
            raise RuntimeError(f"Torrent error: {status.error}")
        if status.has_metadata:
            break
        if time.monotonic() - metadata_started >= metadata_timeout:
            raise TimeoutError(
                "Timed out waiting for torrent metadata. Check the magnet link "
                "and your network connection."
            )
        print(f"Waiting for metadata... Peers: {status.num_peers}", end="\r")
        time.sleep(1)

    print(f"Starting download: {status.name}")
    last_progress = status.total_wanted_done
    last_progress_at = time.monotonic()

    while True:
        status = handle.status()
        if status.error:
            raise RuntimeError(f"Torrent error: {status.error}")
        if status.is_finished:
            break

        now = time.monotonic()
        if status.total_wanted_done > last_progress:
            last_progress = status.total_wanted_done
            last_progress_at = now
        elif now - last_progress_at >= stall_timeout:
            raise TimeoutError(
                f"No download progress for {stall_timeout:g} seconds. "
                f"Connected peers: {status.num_peers}."
            )

        print(
            f"Progress: {_format_progress_bar(status.progress)} "
            f"{status.progress * 100:.2f}% | "
            f"Down: {status.download_rate / 1024:.1f} KiB/s | "
            f"Peers: {status.num_peers}",
            end="\r",
        )

        time.sleep(1)

    handle.pause()
    print(f"\nDownload complete! Files saved to: {destination}")
    return destination


if __name__ == "__main__":
    try:
        magnet = input("Enter Magnet Link: ")
        download_magnet(magnet)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"\nDownload failed: {error}")