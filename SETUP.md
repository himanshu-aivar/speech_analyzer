
# PitchMentor Backend Setup Guide
## 1. System Preparation

````markdown
sudo apt update
sudo apt install software-properties-common
````

## 2. Install Python 3.10

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
python3.10 --version
```

## 3. Create and Activate Virtual Environment

```bash
python3.10 -m venv venv310
source venv310/bin/activate
```

## 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Run the Application

```bash
uvicorn main:app --reload
```

Backend runs at: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

## 6. Managing the Server

Check which process is using port 8000:

```bash
lsof -i :8000
```

Kill the process (replace `12345` with actual PID):

```bash
kill -9 12345
```



