import os
import json
import requests
from collections import Counter
from pathlib import Path
from slack_sdk import WebClient
from pathlib import Path
import shutil
import logging
from slack_sdk.errors import SlackApiError


class SlackListener:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self.webhook_url = os.getenv('SLACK_LISTENER_WEBHOOK_URL')
        assert self.webhook_url is not None or not "", print(
            "SLACK_LISTENER_WEBHOOK_URL env variable needs to bet set")
        self.slack_bot_token = os.getenv('SLACK_BOT_TOKEN')
        assert self.slack_bot_token is not None or not "", print(
            "SLACK_BOT_TOKEN env variable needs to bet set")
        self._suite_status = dict()
        self._test_status = dict()


    def end_test(self, data, result):
        self._test_status[data] = result.passed


    def end_suite(self, data, result):
        self._suite_status[data] = self._test_status
        self._test_status = dict()


    # works with robot but no pabot
    # pabot seems to call this method everyime it passes a suite 
    # which is super awkward
    def close(self):
        attachments = self._build_overall_results_attachment()
        self._send_slack_request(attachments)


    def _build_overall_results_attachment(self):
        print("Building slack block message")
        results = {k: v for test_results in self._suite_status.values()
                   for k, v in test_results.items()}
        return [
            {
                "pretext": "*All Results*",
                "color": "good" if all(results.values()) else "danger",
                "mrkdwn_in": [
                    "pretext"
                ],
                "fields": [
                    {
                        "title": "UI tests",
                        "value": Counter(results.values())[True],
                        "short": True
                    },
                    {
                        "title": "Total test cases",
                        "value": len(results.values()),
                        "short": True
                    },
                    {
                        "title": "Pass percentage",
                        "value": "{0:.2f}%".format(float((Counter(results.values())[True]) / float(len(results))) * 100),
                        "short": True
                    },
                    {
                        "title": "Results",
                        "value": "passed" if all(results.values()) else "failed",
                        "short": True
                    }
                ],
            }]


    def _send_slack_request(self, attachments):
        data = {"attachments": attachments}

        requests.sessions.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=3
        )
        session = requests.Session()

        response = session.post(url=self.webhook_url, data=json.dumps(
            data), headers={'Content-Type': 'application/json'})
        assert response.status_code == 200, print(
            "Response wasn't 200, it was: {}".format({response}))

        print("Sent UI test statistics to #build")

        client = WebClient(token=self.slack_bot_token)

        root = os.getcwd()
        shutil.make_archive('UI-test-report', 'zip', f'{root}/test-results')

        try:
            result = client.files_upload(
                channels="#build",
                file='UI-test-report.zip',
                title='test-report.zip',
                initial_comment="Latest UI test results"
            )
            print(f"Sent test report to #build \n {result}")

        except SlackApiError as e:
            print("Error uploading test report: {}".format(e))

        os.remove('UI-test-report.zip')
