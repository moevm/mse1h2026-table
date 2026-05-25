docker run -d --name httpbin -p 8088:80 kennethreitz/httpbin

cd playground/locust
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

bash run_headless.sh