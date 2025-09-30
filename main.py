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
        disks = []

        for line in output.splitlines()[1:]:  # Пропустить заголовок
            if line.strip():
                parts = line.split(maxsplit=3)
                name = parts[0]
                size = parts[1]
                mountpoint = parts[2] if len(parts) == 4 and parts[2] else ""
                dev_type = parts[-1]
                if dev_type == "disk":
                    disks.append({"name": name, "size": size, "mountpoint": mountpoint})
                # Игнорируем разделы и loop-устройства
        return disks
    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения lsblk: {e}")
        return []
    except Exception as e:
        print(f"Непредвиденная ошибка: {e}")
        return []

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    disks = await get_disks()
    return templates.TemplateResponse("index.html", {"request": request, "disks": disks})

@app.post("/mount")
async def mount_disk(device: str = Form(...), mount_point: str = Form(...)):
    try:
        # Проверяем, есть ли разделы у диска
        output = subprocess.run(
            ["lsblk", "-o", "NAME,TYPE", "-l", "-p", device],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        first_partition = None
        for line in output.splitlines()[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "part":
                    first_partition = parts[0]
                    break
        if not first_partition:
            raise ValueError("У диска нет разделов для монтирования")
        if not os.path.exists(mount_point):
            os.makedirs(mount_point)
        subprocess.run(["sudo", "mount", first_partition, mount_point], check=True)
        return {"status": "success", "message": f"Раздел {first_partition} смонтирован в {mount_point}"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Ошибка монтирования: {e.stderr or str(e)}"}
    except ValueError as e:
        return {"status": "error", "message": str(e)}

@app.delete("/unmount")
async def unmount_disk(device: str = Form(...)):
    try:
        # Находим все точки монтирования для разделов диска
        output = subprocess.run(
            ["lsblk", "-o", "NAME,MOUNTPOINT", "-l", "-p", device],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        mount_points = []
        for line in output.splitlines()[1:]:
            if line.strip():
                parts = line.split(maxsplit=1)
                if len(parts) == 2 and parts[1]:
                    mount_points.append(parts[1])
        if not mount_points:
            raise ValueError("У диска нет смонтированных разделов")
        for mount_point in mount_points:
            subprocess.run(["sudo", "umount", mount_point], check=True)
        return {"status": "success", "message": f"Все разделы диска {device} размонтированы"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Ошибка размонтирования: {e.stderr or str(e)}"}
    except ValueError as e:
        return {"status": "error", "message": str(e)}

@app.post("/format")
async def format_disk(device: str = Form(...), filesystem: str = Form("ext4")):
    try:
        # Защищаем системный диск
        system_disks = ["/dev/nvme0n1"]
        if device in system_disks:
            raise ValueError("Нельзя форматировать системный диск")
        # Проверяем, смонтированы ли какие-либо разделы диска
        output = subprocess.run(
            ["lsblk", "-o", "NAME,MOUNTPOINT", "-l", "-p", device],
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        for line in output.splitlines()[1:]:
            if line.strip():
                parts = line.split(maxsplit=1)
                if len(parts) == 2 and parts[1]:
                    raise ValueError(f"Раздел {parts[0]} смонтирован в {parts[1]}")
        subprocess.run(["sudo", "mkfs", "-t", filesystem, device], check=True)
        return {"status": "success", "message": f"Диск {device} отформатирован как {filesystem}"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Ошибка форматирования: {e.stderr or str(e)}"}
    except ValueError as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.2", port=8000)