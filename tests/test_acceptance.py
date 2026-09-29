import json
import unittest
import urllib.parse
import urllib.request


BACKEND = "http://localhost:8000"
FRONTEND = "http://localhost:3000"


def request_json(url, method="GET", data=None, headers=None):
    body = None
    request_headers = headers or {}

    if data is not None:
        body = json.dumps(data).encode()
        request_headers = {
            **request_headers,
            "Content-Type": "application/json",
        }

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )

    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode())


class ForgeJudgeSmokeTests(unittest.TestCase):

    def test_backend_health(self):
        status, data = request_json(f"{BACKEND}/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "ForgeJudge")

    def test_frontend_is_served(self):
        with urllib.request.urlopen(FRONTEND, timeout=5) as response:
            self.assertEqual(response.status, 200)

    def test_voting_configuration(self):
        status, data = request_json(
            f"{BACKEND}/api/votes/event/1/config"
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["event_id"], 1)
        self.assertTrue(data["configured"])

    def test_randomized_gallery(self):
        _, first = request_json(
            f"{BACKEND}/api/votes/event/1/projects"
        )
        _, second = request_json(
            f"{BACKEND}/api/votes/event/1/projects"
        )

        self.assertGreater(len(first), 0)
        self.assertEqual(
            sorted(project["id"] for project in first),
            sorted(project["id"] for project in second),
        )


if __name__ == "__main__":
    unittest.main()
