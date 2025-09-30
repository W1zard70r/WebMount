from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import subprocess
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

async def get_disks():
    try:
        output = subprocess.run(
            ["lsblk", "-o", "NAME,SIZE,MOUNTPOINT,TYPE", "-l", "-p"],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        # print(output)
        disks = []
        current_disk = None

        for line in output.splitlines()[1:]:  # Skip header
            if line.strip():
                parts = line.split(maxsplit=3)
                # print(parts)
                name = parts[0]
                size = parts[1]
                mountpoint = parts[2] if len(parts) == 4 and parts[2] else ""
                dev_type = parts[-1]
                # print(dev_type)
                if dev_type == "disk":
                    current_disk = {"name": name, "size": size, "mountpoint": mountpoint, "partitions": []}
                    disks.append(current_disk)
                elif dev_type == "part" and current_disk is not None:
                    current_disk["partitions"].append({
                        "name": name,
                        "size": size,
                        "mountpoint": mountpoint
                    })
        # print('\n',disks)
        return disks
    except subprocess.CalledProcessError as e:
        print(f"Error running lsblk: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    disks = await get_disks()
    return templates.TemplateResponse("index.html", {"request": request, "disks": disks})

@app.post("/mount")
async def mount_dist(device: str = Form(...), mount_point: str = Form(...)):
    try:
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        subprocess.run(["sudo", "mount", device, mount_point], check=True)
        return {"status": "success", "message": f"Mounted {device} to {mount_point}"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": str(e)}

@app.delete("/unmount")
async def unmount_disk(mount_point: str = Form(...)):
    try:
        subprocess.run(["sudo", "umount", mount_point], check=True)
        return {"status": "success", "message": f"Unmounted {mount_point}"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": str(e)}

@app.post("/format")
async def format_disk(device: str = Form(...), filesystem: str = Form("ext4")):
    try:
        system_partitions = ["/dev/nvme0n1p7", "/dev/nvme0n1p1"]
        if os.path.ismount(device) or device in system_partitions:
            raise ValueError("Устройство смонтировано или является системно-критическим разделом")
        subprocess.run(["sudo", "mkfs", "-t", filesystem, device], check=True)
        return {"status": "success", "message": f"Formatted {device} as {filesystem}"}
    except (subprocess.CalledProcessError, ValueError) as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.2", port=8000)