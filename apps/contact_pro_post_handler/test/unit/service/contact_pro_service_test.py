# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring, import-outside-toplevel
import pytest
import logging
import json
from dataclasses import dataclass
import urllib3


@dataclass
class ResponseMock:
    status: int
    data: bytes = '{"message": "OK"}'.encode('utf-8')


# pylint: disable=invalid-name, too-few-public-methods
class PoolManagerMock:
    responses = []

    def __init__(self, timeout):
        pass

    @staticmethod
    def set_response(response, assertion, is_invocable_response=False):
        PoolManagerMock.responses.append({
            'response': response,
            'assertion': assertion,
            'is_invocable_response': is_invocable_response
        })

    @staticmethod
    def request(method, url, headers, body=None, fields=None):
        response_and_assert = PoolManagerMock.responses.pop()

        if response_and_assert['assertion']:
            response_and_assert['assertion'](method, url, headers, body, fields)

        if response_and_assert['is_invocable_response']:
            return response_and_assert['response'](method, url, headers, body, fields)

        return response_and_assert['response']


class TestContactProService:
    # pylint: disable=attribute-defined-outside-init
    def contact_pro_service(self, monkeypatch):
        if '_contact_pro_service' not in self.__dict__:
            with monkeypatch.context() as local_m:
                local_m.setattr(urllib3, "PoolManager", PoolManagerMock)

                logger = logging.getLogger()
                from contact_pro_post_handler.service.contact_pro_service import ContactProService
                self._contact_pro_service = ContactProService(
                    username='test-username',
                    password='test-password',
                    base_path='base/path',
                    x_api_key='test-x-api-key',
                    logger=logger
                )

        return self._contact_pro_service

    def test_post_event_to_contact_pro(self, monkeypatch):
        def assert_call(method, url, headers, body, fields):
            assert method == 'POST'
            assert headers['x-api-key'] == 'test-x-api-key'
            assert body == json.dumps({'test': 'test'}).encode('utf-8')
            assert url == 'base/path/endpoint'
            assert fields is None

        PoolManagerMock.set_response(ResponseMock(200, 'TESTID1'.encode('utf-8')), assert_call)

        data = self.contact_pro_service(monkeypatch).post_event_to_contact_pro(
            endpoint_path='endpoint', body={'test': 'test'}
        )

        assert data == 'TESTID1'

    def test_post_event_to_contact_pro_raise_error_if_request_unsuccessful(self, monkeypatch):
        PoolManagerMock.set_response(ResponseMock(400), None)

        from contact_pro_post_handler.service.contact_pro_service import ContactProConnectionException
        with pytest.raises(ContactProConnectionException) as e_info:
            data = self.contact_pro_service(monkeypatch).post_event_to_contact_pro(
                endpoint_path='endpoint', body={'test': 'test'}
            )

    def test_get_event_from_contact_pro(self, monkeypatch):
        def assert_call(method, url, headers, body, fields):
            assert method == 'GET'
            assert headers['x-api-key'] == 'test-x-api-key'
            assert body is None
            assert url == 'base/path/endpoint'
            assert fields == {'test': 'test'}

        PoolManagerMock.set_response(ResponseMock(200, '[]'.encode('utf-8')), assert_call)

        data = self.contact_pro_service(monkeypatch).get_event_from_contact_pro(
            endpoint_path='endpoint', query_fields={'test': 'test'}
        )

        assert data == []

    def test_get_event_from_contact_pro_raise_error_if_request_unsuccessful(self, monkeypatch):
        PoolManagerMock.set_response(ResponseMock(400), None)

        from contact_pro_post_handler.service.contact_pro_service import ContactProConnectionException
        with pytest.raises(ContactProConnectionException) as e_info:
            data = self.contact_pro_service(monkeypatch).get_event_from_contact_pro(
                endpoint_path='endpoint', query_fields={'test': 'test'}
            )

