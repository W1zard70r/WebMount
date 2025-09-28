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
        output = subprocess.run(["lsblk", "-o", "NAME,SIZE,MOUNTPOINT", "-l", "-p"], capture_output=True, text=True).stdout.strip()
        lines = output.splitlines()[1:]  
        disks = []
        for line in lines:
            if line.strip() and not line.startswith('├─') and not line.startswith('└─'): 
                parts = line.split(maxsplit=2)
                name = parts[0]
                size = parts[1]
                mountpoint = parts[2] if len(parts) > 2 else ""
                disks.append({"name": name, "size": size, "mountpoint": mountpoint})
        return disks
    except Exception as e:
        return []


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    disks = get_disks()
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
        if os.path.ismount(device) or "sda" in device:
            raise ValueError("Device is mounted or system disk")
        subprocess.run(["sudo", "mkfs", "-t", filesystem, device], check=True)
        return {"status": "success", "message": f"Formatted {device} as {filesystem}"}
    except (subprocess.CalledProcessError, ValueError) as e:
        return {"status": "error", "message": str(e)}
    

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.2", port=8000)