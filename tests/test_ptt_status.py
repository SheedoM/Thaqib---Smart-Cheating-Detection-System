from src.thaqib.api.ws_manager import manager


def test_ptt_status_lists_connected_client_ids(client, admin_token_headers):
    original = dict(manager.active_connections)
    try:
        manager.active_connections.clear()
        manager.active_connections["control_room_1"] = object()
        manager.active_connections["invigilator_demo_1"] = object()

        response = client.get("/api/v1/ptt/status", headers=admin_token_headers)

        assert response.status_code == 200
        assert response.json() == {
            "connected_count": 2,
            "connected_clients": ["control_room_1", "invigilator_demo_1"],
        }
    finally:
        manager.active_connections.clear()
        manager.active_connections.update(original)
