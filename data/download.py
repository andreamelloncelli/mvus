from pathlib import Path
import wget

debug = False

data_dir = Path("data/drone-tracking-datasets")

detection_dir = data_dir / "dataset4" / "detections"
github_root_url = Path("raw.githubusercontent.com/CenekAlbl/drone-tracking-datasets/master/")

relative_path_ls = [Path(path) for path in [
    "calibration/mate7/mate7.json",
    "calibration/mate10/mate10_2.json",
    "calibration/gopro3/gopro3.json",
    "calibration/p20pro/p20pro.json",
    "calibration/sony5100/sony5100.json",
    "calibration/sonyG/sonyG_2.json",
    "calibration/sony5n_1440x1080/sony5n_1440x1080.json"
]]

def download_repository_file(relative_path):
    url = github_root_url / relative_path
    output_dir = data_dir / relative_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"downloading {relative_path}...")
    print(str(url))
    if (not debug) and (not relative_path.exists()):
        wget.download(f"https://{str(url)}", out=str(output_dir))

if __name__ == "__main__":
    for relative_path in relative_path_ls:
        download_repository_file(relative_path)
