import asyncio
import pytest
import httpx
import websockets
import json
import datetime

@pytest.mark.asyncio
async def test_live_scheduler_loop():
    # Check if live server is accessible; skip if running in offline/CI test environments
    try:
        async with httpx.AsyncClient(timeout=2.0) as check_client:
            time_res = await check_client.get('http://localhost:8000/health/time')
            if time_res.status_code != 200:
                pytest.skip(f"Live server returned status {time_res.status_code}. Skipping live E2E test.")
                return
    except Exception as exc:
        pytest.skip(f"Live backend server is not running on http://localhost:8000 ({exc}). Skipping live E2E test.")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health time check
        time_res = await client.get('http://localhost:8000/health/time')
        assert time_res.status_code == 200, time_res.text
        time_data = time_res.json()
        print('HEALTH TIME:', json.dumps(time_data, indent=2))
        local_time_str = time_data['local_time']
        local_dt = datetime.datetime.fromisoformat(local_time_str)
        weekday_code = time_data['weekday_code']
        
        # 2. Login
        login_res = await client.post('http://localhost:8000/api/v1/auth/login', json={'email': 'admin@hydracontrol.io', 'password': 'SecretPass123!'})
        assert login_res.status_code == 200, login_res.text
        token = login_res.json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        # 3. Hierarchy lookup
        sites_res = await client.get('http://localhost:8000/api/v1/sites', headers=headers)
        site_id = sites_res.json()[0]['id']
        stations_res = await client.get(f'http://localhost:8000/api/v1/stations?site_id={site_id}', headers=headers)
        station_id = stations_res.json()[0]['id']
        controllers_res = await client.get(f'http://localhost:8000/api/v1/controllers?station_id={station_id}', headers=headers)
        controller_id = controllers_res.json()[0]['id']
        motors_res = await client.get(f'http://localhost:8000/api/v1/motors?controller_id={controller_id}', headers=headers)
        motor_id = motors_res.json()[0]['id']
        print(f'Motor ID: {motor_id}, Station ID: {station_id}')

        # 4. WebSocket connection
        ws_url = f'ws://localhost:8000/api/v1/ws?token={token}'
        async with websockets.connect(ws_url) as ws:
            conn_msg = json.loads(await ws.recv())
            print('WS CONNECTED:', conn_msg.get('type'))

            await ws.send(json.dumps({
                'action': 'SUBSCRIBE',
                'channels': [f'station:{station_id}', f'motor:{motor_id}', 'general']
            }))
            sub_msg = json.loads(await ws.recv())
            print('WS SUBSCRIBED:', sub_msg.get('type'))

            # 5. Create TODAY schedule for next minute
            target_time = local_dt + datetime.timedelta(minutes=1)
            sched_time_str = target_time.strftime('%H:%M')
            print(f'Creating TODAY schedule for start_time={sched_time_str}, day={weekday_code}...')

            sched_payload = {
                'station_id': station_id,
                'motor_id': motor_id,
                'name': f'Live Test Schedule {sched_time_str}',
                'start_time': sched_time_str,
                'duration_seconds': 120,
                'days_of_week': [weekday_code],
                'is_active': True
            }
            sched_res = await client.post(f'http://localhost:8000/api/v1/stations/{station_id}/schedules', json=sched_payload, headers=headers)
            assert sched_res.status_code in (200, 201), sched_res.text
            sched_data = sched_res.json()
            schedule_id = sched_data['id']
            print(f'Created schedule {schedule_id} for {sched_time_str}')

            # 6. Listen for NOTIFICATION_RECEIVED
            print(f'Waiting up to 90 seconds for live background scheduler to tick at {sched_time_str}...')
            notification_received = None
            start_wait = datetime.datetime.now()
            while (datetime.datetime.now() - start_wait).total_seconds() < 90:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    event_data = json.loads(raw_msg)
                    ev_name = event_data.get('event') or event_data.get('type')
                    print(f'WS EVENT RECEIVED: {ev_name}')
                    if ev_name == 'NOTIFICATION_RECEIVED':
                        notification_received = event_data
                        print('SUCCESS! NOTIFICATION_RECEIVED MATCHED:')
                        print(json.dumps(event_data, indent=2))
                        break
                except asyncio.TimeoutError:
                    print('... waiting for scheduler tick ...')

            assert notification_received is not None, 'FAILED: Did not receive NOTIFICATION_RECEIVED within 90s'
            print('ALL LIVE CHECKS PASSED!')

if __name__ == '__main__':
    asyncio.run(test_live_scheduler_loop())
