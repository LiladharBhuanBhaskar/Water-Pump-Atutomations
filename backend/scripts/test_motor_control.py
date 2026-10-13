import requests
import time

login_resp = requests.post(
    "http://127.0.0.1:8000/api/v1/auth/login",
    json={"email": "admin@hydracontrol.io", "password": "SecretPass123!"}
)
token = login_resp.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

motors = requests.get("http://127.0.0.1:8000/api/v1/motors", headers=headers).json()
print("Initial motors:", [(m["motor_code"], m["status"]) for m in motors])

pump = motors[0]
print("Starting", pump["motor_code"], "...")
start_resp = requests.post(
    f"http://127.0.0.1:8000/api/v1/motors/{pump['id']}/start",
    json={"duration_seconds": 900, "reason": "TEST_START"},
    headers=headers
)
print("Start response code:", start_resp.status_code)

time.sleep(2.5)

motors_after = requests.get("http://127.0.0.1:8000/api/v1/motors", headers=headers).json()
print("Motors after 2.5s:", [(m["motor_code"], m["status"]) for m in motors_after])

print("Stopping", pump["motor_code"], "...")
stop_resp = requests.post(
    f"http://127.0.0.1:8000/api/v1/motors/{pump['id']}/stop",
    json={"reason": "TEST_STOP"},
    headers=headers
)
print("Stop response code:", stop_resp.status_code)

time.sleep(2.5)

motors_final = requests.get("http://127.0.0.1:8000/api/v1/motors", headers=headers).json()
print("Final motors after stop:", [(m["motor_code"], m["status"]) for m in motors_final])
