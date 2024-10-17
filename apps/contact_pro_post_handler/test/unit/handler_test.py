# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring, import-outside-toplevel
import json


# pylint: disable=invalid-name, too-few-public-methods, unused-argument, too-many-arguments
class TestContactProHandler:
    class ContactProServiceMock:
        GET_EVENT_RESPONSE = []
        POST_EVENT_RESPONSE = 'TESTID1'

        def __init__(self, username, password, base_path, x_api_key, logger):
            pass

        def post_event_to_contact_pro(self, endpoint_path, body):
            return TestContactProHandler.ContactProServiceMock.POST_EVENT_RESPONSE

        def get_event_from_contact_pro(self, endpoint_path, query_fields=None):
            return TestContactProHandler.ContactProServiceMock.GET_EVENT_RESPONSE

    class SSMServiceMock:
        def __init__(self, logger, env):
            pass

        def get_ssm_parameter_with_env(self, parameter_name, with_decryption=True):
            pass

    # pylint: disable=attribute-defined-outside-init
    def get_handler(self, monkeypatch):
        if '_handler' not in self.__dict__:
            with monkeypatch.context() as local_m:
                from contact_pro_post_handler.service import contact_pro_service, ssm_service
                from contact_pro_post_handler import const
                local_m.setattr(contact_pro_service, "ContactProService", self.ContactProServiceMock)
                local_m.setattr(ssm_service, "SSMService", self.SSMServiceMock)
                local_m.setattr(const, "get_global_environment", lambda: "test-env")

                from contact_pro_post_handler import main
                self._handler = main

        return self._handler

    def test_is_not_duplicate_true_if_first_try(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        test_event = {
            'unique_request_id': "test1"
        }
        test_event_attributes = {
            'ApproximateReceiveCount': '1'
        }

        assert local_handler.is_not_duplicate(test_event, test_event_attributes)

    def test_is_not_duplicate_true_if_second_try_and_record_not_exist(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        test_event = {
            'unique_request_id': "test1",
            'api_path': '/get',
            'api_get_body': {}
        }
        test_event_attributes = {
            'ApproximateReceiveCount': '2'
        }

        assert local_handler.is_not_duplicate(test_event, test_event_attributes)

    def test_is_not_duplicate_false_if_second_try_and_record_exists(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        TestContactProHandler.ContactProServiceMock.GET_EVENT_RESPONSE = ['existing-record']
        test_event = {
            'unique_request_id': "test1",
            'api_path': '/get',
            'api_get_body': {}
        }
        test_event_attributes = {
            'ApproximateReceiveCount': '2'
        }

        assert not local_handler.is_not_duplicate(test_event, test_event_attributes)

    def test_is_not_duplicate_false_if_first_try_bridge_duplicate_and_record_exists(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        TestContactProHandler.ContactProServiceMock.GET_EVENT_RESPONSE = ['existing-record']
        test_event = {
            'unique_request_id': "test1",
            'api_path': '/get',
            'api_get_body': {},
            'duplicate_event': True
        }
        test_event_attributes = {
            'ApproximateReceiveCount': '2'
        }

        assert not local_handler.is_not_duplicate(test_event, test_event_attributes)

    def test_lambda_handler(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        test_event = {
            'Records': [
                {
                    'body': json.dumps({
                        'unique_request_id': "test1",
                        'api_path': '/get',
                        'api_post_body': {},
                        'api_get_body': {}
                    }),
                    'attributes': {
                        'ApproximateReceiveCount': '1'
                    }
                }
            ]
        }

        local_handler.lambda_handler(test_event, None)

    def test_lambda_handler_not_fail_in_case_of_duplicate(self, monkeypatch):
        local_handler = self.get_handler(monkeypatch)
        test_event = {
            'Records': [
                {
                    'body': json.dumps({
                        'unique_request_id': "test1",
                        'api_path': '/get',
                        'api_post_body': {},
                        'api_get_body': {}
                    }),
                    'attributes': {
                        'ApproximateReceiveCount': '2'
                    }
                }
            ]
        }

        local_handler.lambda_handler(test_event, None)
