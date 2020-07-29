import copy
import logging
import sys
import unittest

import pytest
from hamcrest import assert_that, empty, has_length, instance_of, equal_to, none, is_
from oauthlib.oauth2 import InvalidGrantError
from requests import Response

from sequoia import criteria, auth
from sequoia import error
from sequoia.auth import TokenCache, AuthType
from sequoia.client import Client, ResponseBuilder
from sequoia.criteria import Criteria, Inclusion
from tests import mocking

if sys.version_info[0] == 2:
    from mock import patch
else:
    from unittest.mock import patch

logging.basicConfig(level=logging.DEBUG)


class TestResourceEndpointProxy(unittest.TestCase):

    def setUp(self):
        TokenCache._token_storage = {}
        self.mock = mocking.bootstrap_mock()
        self.client = Client('http://mock-registry/services/testmock',
                             grant_client_id='piksel-workflow',
                             grant_client_secret='blablabla',
                             adapters=[('http://', self.mock)])

    def test_returns_mocked_profile(self):
        mocking.add_get_mapping_for(self.mock, 'workflow', 'valid_workflow_profile_response')
        mocking.add_get_mapping_for(self.mock, 'descriptor', 'valid_workflow_profile_response')
        self.client = Client('http://mock-registry/services/testmock',
                             grant_client_id='piksel-workflow',
                             grant_client_secret='blablabla',
                             adapters=[('http://', self.mock)], model_resolution='all')
        under_test = self.client.workflow.profiles

        response = under_test.read('testmock', 'testmock:profile-1')

        assert_that(response.resources[0]['title'], 'profile-1')

    def test_delete(self):
        mocking.add_delete_mapping_for(self.mock, "workflow")
        under_test = self.client.workflow.profiles

        response = under_test.delete("testmock", "testmock:profile-1")

        assert_that(response.status, 200)
        assert_that(response.resources, empty())

    def test_delete_collection_resources(self):
        mocking.add_delete_mapping_for(self.mock, "workflow")
        under_test = self.client.workflow.profiles
        response = under_test.delete("testmock", ['testmock:profile-1', 'testmock:profile-2'])
        assert_that(response.status, 200)
        assert_that(response.resources, empty())

    def test_delete_collection_resources_with_only_one_resource_in_the_colection(self):
        mocking.add_delete_mapping_for(self.mock, "workflow")
        under_test = self.client.workflow.profiles
        response = under_test.delete("testmock", ['testmock:profile-1'])
        assert_that(response.status, 200)
        assert_that(response.resources, empty())

    def test_browse_assets_with_criteria_returns_mocked_assets(self):
        mocking.add_get_mapping_for(self.mock, 'metadata', 'valid_metadata_assets_response')
        my_criteria = criteria.Criteria()
        my_criteria.add(criterion=criteria.StringExpressionFactory.field('contentRef').equal_to('theContentRef'))
        under_test = self.client.metadata.assets

        response = under_test.browse('testmock', my_criteria)

        assert_that(response.resources, has_length(4))
        assert_that(response.resources[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')

    def test_browse_assets_with_fields_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?fields=name\%2Cref&owner=testmock&withContentRef=theContentRef',
                                        'valid_metadata_assets_response')
        my_criteria = criteria.Criteria()
        my_criteria.add(criterion=criteria.StringExpressionFactory.field('contentRef').equal_to('theContentRef'))
        under_test = self.client.metadata.assets

        response = under_test.browse('testmock', my_criteria, fields=['name', 'ref'])

        assert_that(response.resources, has_length(4))
        assert_that(response.resources[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')

    def test_browse_assets_with_query_string_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&owner=testmock',
                                        'valid_metadata_assets_response')
        under_test = self.client.metadata.assets

        response = under_test.browse('testmock', query_string='withContentRef=theContentRef')

        assert_that(response.resources, has_length(4))
        assert_that(response.resources[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')

    def test_browse_assets_paging_with_continue_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?continue=true&perPage=2&owner=testmock',
                                        'pagination_continue_page_1')
        mocking.add_get_mapping_for_url(self.mock,
                                        '/data/contents\?continue=00abcdefghijklmnopqrstuvwxyz11&owner=test&perPage=2',
                                        'pagination_continue_page_2')
        mocking.add_get_mapping_for_url(self.mock,
                                        '/data/contents\?continue=00abcdefghijklmnopqrstuvwxyz22&owner=test&perPage=2',
                                        'pagination_continue_page_3')

        under_test = self.client.metadata.contents

        under_test_browse = under_test.browse('testmock', query_string='continue=true&perPage=2')

        response_list = [response for response in under_test_browse]

        assert_that(response_list, has_length(3))
        assert_that(response_list[0].resources, has_length(2))
        assert_that(response_list[1].resources, has_length(2))
        assert_that(response_list[2].resources, has_length(1))
        assert_that(response_list[0].resources[0]['name'], is_('001436b2-93b7-43c5-89a3-b95ceb50aa73'))
        assert_that(response_list[0].resources[1]['name'], is_('001436b2-93b7-43c5-89a3-b95ceb50aa73_aligned_primary'))
        assert_that(response_list[1].resources[0]['name'], is_('001436b2-93b7-43c5-89a3-b95ceb50aa73_primary'))
        assert_that(response_list[1].resources[1]['name'], is_('001436b2-93b7-43c5-89a3-b95ceb50aa73_textless'))
        assert_that(response_list[2].resources[0]['name'], is_('0065ab4e-caf9-4096-8b3b-df4a8f3f19dd_aligned_primary'))

    def test_browse_assets_with_model_query_string_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&owner=testmock',
                                        'valid_metadata_assets_response')
        mocking.add_get_mapping_for_url(self.mock,
                                        'descriptor',
                                        'workflow_descriptor_raw')
        self.client = Client('http://mock-registry/services/testmock',
                             grant_client_id='piksel-workflow',
                             grant_client_secret='blablabla',
                             adapters=[('http://', self.mock)], model_resolution='all')
        under_test = self.client.metadata.assets

        response = under_test.browse('testmock', query_string='withContentRef=theContentRef')

        assert_that(response.resources, has_length(4))
        assert_that(response.resources[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')
        assert_that(response.model[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')

    def test_browse_linked_resources_with_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets,offers&owner=testmock',
                                        'content_with_more_than_1page_linked_assets')
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?fields=ref%2Cname%2CcontentRef%2Ctype%2CmediaType%2Curl%2CfileFormat%2Ctitle%2CfileSize%2Ctags&count=true&withContentRef=test%3AcontentsToChecktesting1&page=2&perPage=100',
                                        'linked_assets_second_page')
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/offers\?fields=ref%2Cname%2Ctitle%2CcontentRefs&count=true&withContentRefs=test%3AcontentsToChecktesting1&page=2&perPage=100',
                                        'linked_offers_second_page')

        under_test = self.client.metadata.contents

        contents_response = under_test.browse('testmock', query_string='include=assets,offers')

        asset_linked = contents_response.linked('assets')
        offers_linked = contents_response.linked('offers')

        assert_that(contents_response.resources, has_length(1))
        assert_that(contents_response.resources[0]['name'], is_('contentsToChecktesting1'))

        assert_that(len(asset_linked.resources), is_(100))
        assert_that(asset_linked.resources[50]['name'], is_('assetsToTest1testing53'))
        assert_that(len(offers_linked.resources), is_(100))
        assert_that(offers_linked.resources[50]['name'], is_('offersToTest1testing53'))

        asset_linked_pages = [page for page in contents_response.linked('assets')]
        assert_that(len(asset_linked_pages[0]), is_(100))
        assert_that(len(asset_linked_pages[1]), is_(1))

        offers_linked_pages = [page for page in contents_response.linked('offers')]
        assert_that(len(offers_linked_pages[0]), is_(100))
        assert_that(len(offers_linked_pages[1]), is_(1))

        expected_requests = [{'path': '/services/testmock', 'query': ''},
                             {'path': '/oauth/token', 'query': ''},
                             {'path': '/data/contents', 'query': 'include=assets,offers&owner=testmock'},
                             {'path': '/data/assets',
                              'query': 'fields=ref%2cname%2ccontentref%2ctype%2cmediatype%2curl%2cfileformat%2ctitle%2cfilesize%2ctags&count=true&withcontentref=test%3acontentstochecktesting1&page=2&perpage=100&owner=testmock'},
                             {'path': '/data/offers',
                              'query': 'fields=ref%2cname%2ctitle%2ccontentrefs&count=true&withcontentrefs=test%3acontentstochecktesting1&page=2&perpage=100&owner=testmock'}]

        performed_requests = [{'path': r.path, 'query': r.query} for r in self.mock.request_history]
        assert_that(performed_requests, is_(expected_requests))

    def test_browse_linked_resources_without_inclusions_then_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?owner=testmock',
                                        'content_with_more_than_1page_linked_assets_and_next_without_inclusions')
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?fields=ref%2Cname%2CcontentRef%2Ctype%2CmediaType%2Curl%2CfileFormat%2Ctitle%2CfileSize%2Ctags&count=true&withContentRef=test%3AcontentsToChecktesting1&page=2&perPage=100',
                                        'linked_assets_second_page')

        under_test = self.client.metadata.contents

        contents_response = under_test.browse('testmock')

        # asset_linked = contents_response.linked('assets')

        # assert_that(contents_response.resources, has_length(2))
        #
        # assert_that(len(asset_linked.data()), is_(106))
        # assert_that(asset_linked.data()[50]['name'], is_('671afede-7a2e-47c9-8541-b854c68e604a'))

        # asset_linked_pages = [page for page in contents_response.linked('assets')]
        # # assert_that(len(asset_linked_pages[0]), is_(100))
        # # assert_that(len(asset_linked_pages[1]), is_(1))

    def test_browse_linked_resources_with_more_than_one_page_goes_throw_several_pages(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock',
                                        'pagination_main_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=2&perPage=100',
                                        'pagination_main_second_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=3&perPage=100',
                                        'pagination_main_third_page')

        under_test = self.client.metadata.contents

        contents_response = under_test.browse('testmock', query_string='include=assets')

        asset_linked = contents_response.linked('assets')

        assert_that(contents_response.resources, has_length(100))
        assert_that(contents_response.resources[0]['name'], is_('0968d155-77ec-450c-ae68-47f8936e2121'))
        assert_that(len(asset_linked.resources), is_(100))
        assert_that(asset_linked.resources[50]['name'], is_('437366a3-a2c5-4633-803c-72dfcb4366f4'))

        asset_linked_pages = [page for page in contents_response.linked('assets')]
        assert_that(len(asset_linked_pages[0]), is_(100))
        assert_that(len(asset_linked_pages[1]), is_(157))
        assert_that(len(asset_linked_pages[2]), is_(46))

        expected_requests = [{'path': '/services/testmock', 'query': ''},
                             {'path': '/oauth/token', 'query': ''},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=2&perpage=100'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=3&perpage=100'}]

        performed_requests = [{'path': r.path, 'query': r.query} for r in self.mock.request_history]
        assert_that(performed_requests, is_(expected_requests))

    def test_cache_modified_while_other_iterator_is_browsing(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock',
                                        'pagination_main_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=2&perPage=100',
                                        'pagination_main_second_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=3&perPage=100',
                                        'pagination_main_third_page')

        under_test = self.client.metadata.contents

        contents_response = under_test.browse('testmock', query_string='include=assets')

        response_count = 0
        for response in contents_response:
            response_count += len(response.resources)
            inner_response_count = 0
            for inner_response in contents_response:
                inner_response_count += len(inner_response.resources)
            assert_that(inner_response_count, is_(228))

        assert_that(response_count, is_(228))

        expected_requests = [{'path': '/services/testmock', 'query': ''},
                             {'path': '/oauth/token', 'query': ''},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=2&perpage=100'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=3&perpage=100'}]

        performed_requests = [{'path': r.path, 'query': r.query} for r in self.mock.request_history]
        assert_that(performed_requests, is_(expected_requests))

    def test_browse_linked_resources_with_prefetch_and_more_than_one_page_goes_throw_several_pages(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock',
                                        'pagination_main_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=2&perPage=100',
                                        'pagination_main_second_page')

        mocking.add_get_mapping_for_url(self.mock,
                                        'data/contents\?include=assets&owner=testmock&page=3&perPage=100',
                                        'pagination_main_third_page')

        under_test = self.client.metadata.contents

        contents_response = under_test.browse('testmock', query_string='include=assets', prefetch_pages=3)

        asset_linked = contents_response.linked('assets')

        assert_that(contents_response.resources, has_length(100))
        assert_that(contents_response.resources[0]['name'], is_('0968d155-77ec-450c-ae68-47f8936e2121'))
        assert_that(len(asset_linked.resources), is_(100))
        assert_that(asset_linked.resources[50]['name'], is_('437366a3-a2c5-4633-803c-72dfcb4366f4'))

        asset_linked_pages = [page for page in contents_response.linked('assets')]
        assert_that(len(asset_linked_pages[0]), is_(100))
        assert_that(len(asset_linked_pages[1]), is_(157))
        assert_that(len(asset_linked_pages[2]), is_(46))

        expected_requests = [{'path': '/services/testmock', 'query': ''},
                             {'path': '/oauth/token', 'query': ''},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=2&perpage=100'},
                             {'path': '/data/contents', 'query': 'include=assets&owner=testmock&page=3&perpage=100'}]

        performed_requests = [{'path': r.path, 'query': r.query} for r in self.mock.request_history]
        assert_that(performed_requests, is_(expected_requests))

    def test_browse_assets_with_paging_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&perPage=2&owner=testmock',
                                        'valid_metadata_assets_response_page_1')
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?owner=testmock&withContentRef=testmock&page=2&perPage=2',
                                        'valid_metadata_assets_response_page_2')
        under_test = self.client.metadata.assets

        response_list = [response
                         for response in under_test.browse('testmock',
                                                           query_string='withContentRef=theContentRef&perPage=2')]

        assert_that(response_list, has_length(2))
        assert_that(response_list[0].resources, has_length(2))
        assert_that(response_list[1].resources, has_length(2))
        assert_that(response_list[0].resources[0]['name'], is_('016b9e5f-c184-48ea-a5e2-6e6bc2d62791'))
        assert_that(response_list[0].resources[1]['name'], is_('192e78ad-25d1-47f8-b539-19053a2b4a6f'))
        assert_that(response_list[1].resources[0]['name'], is_('3bf33965-41fe-4f94-8aa9-63b6b8a379da'))
        assert_that(response_list[1].resources[1]['name'], is_('44c6170a-2c03-42ce-bfa3-101fec955188'))

    def test_browse_assets_with_paging_and_inclusions_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&perPage=2&include=content&owner=testmock',
                                        'valid_metadata_assets_response_with_include_page_1')
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?owner=testmock&withContentRef=testmock&page=2&perPage=2&include=content',
                                        'valid_metadata_assets_response_with_include_page_2')
        under_test = self.client.metadata.assets

        inclusion_contents = criteria.Criteria().add(inclusion=criteria.Inclusion.resource('content'))

        response_list = [response
                         for response in under_test.browse('testmock',
                                                           query_string='withContentRef=theContentRef&perPage=2',
                                                           criteria=inclusion_contents)]

        assert_that(response_list, has_length(2))
        assert_that(response_list[0].resources, has_length(2))
        assert_that(response_list[1].resources, has_length(2))
        assert_that(response_list[0].resources[0]['name'], is_('016b9e5f-c184-48ea-a5e2-6e6bc2d62791'))
        assert_that(response_list[0].resources[1]['name'], is_('192e78ad-25d1-47f8-b539-19053a2b4a6f'))
        assert_that(response_list[1].resources[0]['name'], is_('3bf33965-41fe-4f94-8aa9-63b6b8a379da'))
        assert_that(response_list[1].resources[1]['name'], is_('44c6170a-2c03-42ce-bfa3-101fec955188'))

        expected_requests = \
            [{'path': '/services/testmock', 'query': ''},
             {'path': '/oauth/token', 'query': ''},
             {'path': '/data/assets', 'query': 'withcontentref=thecontentref&perpage=2&include=content&owner=testmock'},
             {'path': '/data/assets', 'query': 'owner=testmock&withcontentref=testmock&page=2&perpage=2&include=content'}]

        performed_requests = [{'path': r.path, 'query': r.query} for r in self.mock.request_history]
        assert_that(performed_requests, is_(expected_requests))


    def test_browse_assets_with_iteration_and_one_page_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&perPage=2&owner=testmock',
                                        'valid_metadata_assets_response_page_2')
        under_test = self.client.metadata.assets

        response_list = [response
                         for response in under_test.browse('testmock',
                                                           query_string='withContentRef=theContentRef&perPage=2')]

        assert_that(response_list, has_length(1))
        assert_that(response_list[0].resources, has_length(2))
        assert_that(response_list[0].resources[0]['name'], is_('3bf33965-41fe-4f94-8aa9-63b6b8a379da'))
        assert_that(response_list[0].resources[1]['name'], is_('44c6170a-2c03-42ce-bfa3-101fec955188'))

    def test_browse_assets_with_iteration_and_prefetch_2_and_one_page_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&perPage=2&owner=testmock',
                                        'valid_metadata_assets_response_page_2')
        under_test = self.client.metadata.assets

        response_list = [response
                         for response in under_test.browse('testmock',
                                                           query_string='withContentRef=theContentRef&perPage=2',
                                                           prefetch_pages=2)]

        assert_that(response_list, has_length(1))
        assert_that(response_list[0].resources, has_length(2))
        assert_that(response_list[0].resources[0]['name'], is_('3bf33965-41fe-4f94-8aa9-63b6b8a379da'))
        assert_that(response_list[0].resources[1]['name'], is_('44c6170a-2c03-42ce-bfa3-101fec955188'))

    def test_browse_assets_with_query_string_and_criteria_returns_mocked_assets(self):
        mocking.add_get_mapping_for_url(self.mock,
                                        'data/assets\?withContentRef=theContentRef&owner=testmock&withType=type',
                                        'valid_metadata_assets_response')
        under_test = self.client.metadata.assets
        a_criteria = criteria.Criteria().add(criterion=criteria.StringExpressionFactory.field('type').equal_to('type'))

        response = under_test.browse('testmock', criteria=a_criteria, query_string='withContentRef=theContentRef')

        assert_that(response.resources, has_length(4))
        assert_that(response.resources[0]['name'], '016b9e5f-c184-48ea-a5e2-6e6bc2d62791')

    def test_update_asset_with_wrong_reference_should_raise_an_error(self):
        under_test = self.client.metadata.assets

        with pytest.raises(error.ReferencesMismatchException) as e:
            under_test.update('testmock',
                              '[{"ref":"reference", "owner":"testmock", "name":"reference"}]',
                              'testmock:reference',
                              'version')

        assert_that(e.value.message,
                    'Reference to update testmock:reference does not match with the resource reference reference.')

    def test_update_asset_with_no_reference_should_raise_an_error(self):
        under_test = self.client.metadata.assets

        with pytest.raises(error.ReferencesMismatchException) as e:
            under_test.update('testmock', '[{"name":"test", "owner":"testmock"}]', 'testmock:reference',
                              'version')

        assert_that(e.value.message,
                    'Reference to update testmock:reference does not match with the resource reference. Resource does not contain ref, owner or name')

    def test_update_asset_with_wrong_owner_should_raise_an_error(self):
        under_test = self.client.metadata.assets

        with pytest.raises(error.ReferencesMismatchException) as e:
            under_test.update('testmock',
                              '[{"name":"reference", "owner":"test", "ref":"testmock:reference"}]',
                              'testmock:reference',
                              'version')

        assert e.value.message == 'Reference to update testmock:reference does not match with the resource reference test:reference.'

    def test_update_asset_with_correct_values_should_update_resource(self):
        mocking.add_put_mapping_for(self.mock, 'metadata', 'valid_metadata_assets_response')
        under_test = self.client.metadata.assets
        under_test.update('testmock',
                          '[{"name":"reference", "owner":"testmock", "ref":"testmock:reference"}]',
                          'testmock:reference',
                          'version')

    @patch('requests.sessions.Session.request')
    @patch('sequoia.auth.requests_oauthlib.OAuth2Session.fetch_token')
    def test_client_given_redirect_should_redirect(self, mock_fetch_token, mock_request):
        redirect_response = Response()
        redirect_response.status_code = 301
        redirect_response.headers = {'location': 'https://mock-registry/services/testmock'}
        valid_registry_response = Response()
        valid_registry_response.status_code = 200
        with open(mocking.__location__ + "/test_files/%s.json" % 'valid_registry_response') as file:
            valid_registry_response._content = file.read().encode('UTF-8')
        mock_request.side_effect = [redirect_response, valid_registry_response]
        mock_fetch_token.return_value = "validToken"

        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla')

        assert_that(client._registry, has_length(4))
        calls = mock_request.call_args_list
        assert_that(calls[0][0][1], 'http://mock-registry/services/testmock')
        assert_that(calls[1][0][1], 'https://mock-registry/services/testmock')


class TestBusinessEndpointProxy(unittest.TestCase):

    def setUp(self):
        self.mock = mocking.bootstrap_mock()
        self.client_with_auth = Client('http://mock-registry/services/testmock',
                                       grant_client_id='piksel-workflow',
                                       grant_client_secret='blablabla',
                                       adapters=[('http://', self.mock)])
        self.client_without_auth = Client('http://mock-registry/services/testmock', adapters=[('http://', self.mock)],
                                          auth_type=auth.AuthType.NO_AUTH)

    def test_store_validation_contents_returns_mocked_response_succesful_validation(self):
        mocking.add_post_mapping_for(self.mock, 'validation', 'validation_response_succeded')
        mock_rule = 'rule_mocked'
        mock_content = mocked_content_for_validation
        under_test = self.client_without_auth.validation

        response = under_test.business('/$service/$owner/$ref$params').store(service='v', owner='test',
                                                                             content=mock_content,
                                                                             ref=mock_rule,
                                                                             params={'validation': 'full'})

        assert_that(response.data['message'], 'Validation Succeded')
        assert_that(response.resources, none())

    def test_browse_flow_progress_execution_returns_mocked_response_succesful_validation(self):
        mocking.add_get_mapping_for(self.mock, 'workflow', 'valid_workflow_flow_execution_progress_response_not_found')
        ref_mocked = 'flow-execution-that-not-exists'
        under_test = self.client_with_auth.workflow

        response = under_test.business('/$service/$owner:$ref').browse(service='flow-execution-progress',
                                                                       owner='testmock', ref=ref_mocked)

        assert_that(response.data['message'], 'FlowExecution not found')

    @patch('requests.sessions.Session.request')
    @patch('requests_oauthlib.OAuth2Session.fetch_token')
    def test_client_given_redirect_should_redirect(self, mock_fetch_token, mock_request):
        redirect_response = Response()
        redirect_response.status_code = 301
        redirect_response.headers = {'location': 'https://mock-registry/services/testmock'}
        valid_registry_response = Response()
        valid_registry_response.status_code = 200
        with open(mocking.__location__ + "/test_files/%s.json" % 'valid_registry_response') as file:
            valid_registry_response._content = file.read().encode('UTF-8')
        mock_request.side_effect = [redirect_response, valid_registry_response]
        mock_fetch_token.return_value = "validToken"

        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla')

        assert_that(client._registry, has_length(4))
        calls = mock_request.call_args_list
        assert_that(calls[0][0][1], 'http://mock-registry/services/testmock')
        assert_that(calls[1][0][1], 'https://mock-registry/services/testmock')

class TestClient(unittest.TestCase):
    def setUp(self):
        self.mock = mocking.bootstrap_mock()
        TokenCache._token_storage = {}
        self.anAuth = auth.AuthFactory.create(grant_client_id="client_id",
                                grant_client_secret="client_secret")

    def test_fetch_token_given_there_is_an_error_fetching_the_token_then_client_error_is_raised(self):
        mocking.add_post_mapping_for(self.mock, 'identity', 'error_identity_response')

        with pytest.raises(error.AuthorisationError) as client_error:
            Client("http://mock-registry/services/testmock",
                   grant_client_id="piksel-workflow",
                   grant_client_secret="blablabla",
                   adapters=[("http://", self.mock)])

        assert_that(client_error.value.cause, instance_of(InvalidGrantError))

        assert_that(client_error.value.args[0],
                    '(invalid_grant) The provided authorization grant (e.g., authorization code, resource owner'
                    ' credentials) or refresh token is invalid, expired, revoked, does not match the redirection URI '
                    'used in the authorization request, or was issued to another client.')

    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_service_proxy_with_dictionary_notation(self, mock_oauth2_wrapper, mock_registry,
                                                           mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        mock_registry.return_value.__getitem__.side_effect = [mock_registry, 'service-with-dash']
        service_proxy = Client('http://mock-registry/services/testmock',
                               grant_client_id='piksel-workflow',
                               grant_client_secret='blablabla',
                               adapters=[('http://', self.mock)])['service-with-dash']
        assert_that(service_proxy._service, equal_to('service-with-dash'))
        assert_that(service_proxy._http, equal_to(mock_http_executor))

    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_endpoint_proxy_with_dictionary_notation(self, mock_oauth2_wrapper, mock_registry,
                                                            mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        endpoint_proxy = Client('http://mock-registry/services/testmock',
                                grant_client_id='piksel-workflow',
                                grant_client_secret='blablabla',
                                adapters=[('http://', self.mock)])['service-with-dash']['resource-with-dash']
        assert_that(endpoint_proxy.resource, equal_to('resource-with-dash'))

    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_client_with_correlation_id(self, mock_oauth2_wrapper, mock_registry, mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla',
                        adapters=[('http://', self.mock)],
                        correlation_id="user_id/application_id/1234567890")

        assert_that(client._correlation_id, equal_to('user_id/application_id/1234567890'))

    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_client_generate_correlation_id(self, mock_oauth2_wrapper, mock_registry, mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla',
                        adapters=[('http://', self.mock)],
                        user_id='user_id',
                        application_id='application_id',
                        transaction_id='1234567890')

        assert_that(client._correlation_id, equal_to('user_id/application_id/1234567890'))

    @patch('uuid.uuid4')
    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_client_generate_correlation_id_with_autogenerated_transaction_id(self, mock_oauth2_wrapper,
                                                                                     mock_registry, mock_http_executor,
                                                                                     mock_uuid):
        mock_http_executor.return_value = mock_http_executor
        mock_uuid.return_value = '0987654321'
        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla',
                        adapters=[('http://', self.mock)],
                        user_id='user_id',
                        application_id='application_id')

        assert_that(client._correlation_id, equal_to('user_id/application_id/0987654321'))

    @patch("sequoia.http.HttpExecutor")
    @patch("sequoia.registry.Registry")
    @patch("sequoia.auth.OAuth2SessionTokenManagementWrapper")
    def test_create_client_should_prioritizise_correlation_id_over_arguments_to_build_it(self, mock_oauth2_wrapper,
                                                                                         mock_registry,
                                                                                         mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        client = Client('http://mock-registry/services/testmock',
                        grant_client_id='piksel-workflow',
                        grant_client_secret='blablabla',
                        adapters=[('http://', self.mock)],
                        correlation_id="user_id/application_id/1234567890",
                        user_id='another_user_id',
                        application_id='another_application_id',
                        transaction_id='another_transaction_id')

        assert_that(client._correlation_id, equal_to('user_id/application_id/1234567890'))

    @patch("sequoia.http.HttpExecutor")
    def test_create_client_should_create_session_with_certs_when_auth_type_is_mutual(self, mock_http_executor):
        mock_http_executor.return_value = mock_http_executor
        client_cert = '/cert_path/client_cert.pm'
        client_key = '/cert_path/client_key.pm'
        server_cert = '/cert_path/server_cert.pm'

        client = Client('http://mock-registry/services/testmock',
                        auth_type=AuthType.MUTUAL,
                        client_cert=client_cert,
                        client_key=client_key,
                        server_cert=server_cert,
                        content_type="application/json")

        mock_http_executor.assert_called_with(
            client._auth,
            backoff_strategy=None,
            content_type='application/json',
            correlation_id=None,
            proxies=None,
            request_timeout=240,
            session = client._auth.session,
            user_agent=None)
        assert_that(client._auth.session.cert, equal_to((client_cert, client_key)))
        assert_that(client._auth.session.verify, equal_to(server_cert))


class TestResponseBuilder(unittest.TestCase):

    def test(self):
        under_test = ResponseBuilder(descriptor=mock_model,
                                     criteria=Criteria().add(inclusion=Inclusion.resource('directlyLinkedResources')))

        result = under_test.build(mock_response, 'pluralResources')

        assert_that(result, has_length(3))
        assert_that(result[0]['directlyLinkedResources'], has_length(1))
        assert_that(result[1]['directlyLinkedResources'], has_length(1))
        assert_that(result[2]['directlyLinkedResources'], none())

    def test_when_included_is_not_linked(self):
        under_test = ResponseBuilder(descriptor=mock_model,
                                     criteria=Criteria().add(
                                         inclusion=Inclusion.resource('directlyLinkedResources')).add(
                                         inclusion=Inclusion.resource('anotherLinkedResource')))

        result = under_test.build(mock_response, 'pluralResources')
        assert_that(result, has_length(3))
        assert_that(result[0]['directlyLinkedResources'], has_length(1))
        assert_that(result[1]['directlyLinkedResources'], has_length(1))
        assert_that(result[2]['directlyLinkedResources'], none())

    def test_when_resource_not_in_response_then_return_none(self):
        under_test = ResponseBuilder(descriptor=mock_model,
                                     criteria=Criteria().add(inclusion=Inclusion.resource('directlyLinkedResources')))

        result = under_test.build(mock_response, 'not_in_response_Resources')

        assert_that(result, none())

    def test_when_linked_cannot_be_found_in_meta(self):
        under_test = ResponseBuilder(descriptor=mock_model,
                                     criteria=Criteria().add(inclusion=Inclusion.resource('resourceNotListedInMeta')))

        result = under_test.build(mock_response_linked_resource_not_in_meta, 'pluralResources')

        assert_that(result, has_length(1))
        assert_that(result[0]['resourceNotListedInMeta'], none())

    def test_when_linked_does_not_include_ref_field(self):
        under_test = ResponseBuilder(descriptor=mock_model,
                                     criteria=Criteria().add(
                                         inclusion=Inclusion.resource('directlyLinkedResources')).add(
                                         inclusion=Inclusion.resource('anotherLinkedResource')))
        mock_response_without_ref = copy.deepcopy(mock_response)
        mock_response_without_ref['linked']['directlyLinkedResources'] = [self._remove_ref(resource) for resource in
                                                                          mock_response_without_ref['linked'][
                                                                              'directlyLinkedResources']]

        result = under_test.build(mock_response_without_ref, 'pluralResources')
        assert_that(result, has_length(3))
        assert_that(result[0]['directlyLinkedResources'], none())
        assert_that(result[1]['directlyLinkedResources'], none())
        assert_that(result[2]['directlyLinkedResources'], none())

    def _remove_ref(self, entry):
        del entry['ref']
        return entry


mock_model = {'resourcefuls': {
    'pluralResources': {'singularName': 'singularResource', 'relationships': {'parent': {'fields': ['ref']},
                                                                              'anotherLinkedResources': {
                                                                                  'fieldNamePath': 'anotherLinkedResourceRef'
                                                                              },
                                                                              'directlyLinkedResources': {
                                                                                  'fieldNamePath': 'directlyLinkedResourceRef'}}},
    'directlyLinkedResources': {'singularName': 'directlyLinkedresource'}}}

mock_response = {
    "meta": {
        "linked": {
            "categories": [
                {
                    "request": "/data/categories/demo:genre_animation?fields=ref%2Ctitle%2CparentRef%2Cscheme%2Cvalue%2Cactive"
                }
            ]
        }
    },
    "pluralResources": [
        {
            "ref": "demo:resource_one",
            "alternativeIdentifiers": {},
            "owner": "demo",
            "name": "resource_one",
            "title": "Bella and the Bulldogs: Personal Foul",
            "localisedTitle": {},
            "tags": [
                "viacom"
            ],
            "custom": {
                "mood": "0",
                "valence": [],
                "themes": [],
                "genres": []
            },
            "type": "episode",
            "sortTitle": "Bella and the Bulldogs: Personal Foul",
            "releaseYear": 2015,
            "firstAiredAt": "2015-10-14T00:00:00.000Z",
            "duration": "PT1358S",
            "ratings": {
                "MPAA": "R"
            },
            "active": True,
            "memberRefs": [],
            "parentRef": "demo:bella_and_the_bulldogs",
            "directlyLinkedResourceRef": [
                "demo:genre_animation"
            ],
            "providerRef": "demo:nickelodeon"
        },
        {
            "ref": "demo:resource_two",
            "alternativeIdentifiers": {},
            "owner": "demo",
            "name": "resource_two",
            "title": "Masterchef",
            "localisedTitle": {},
            "tags": [
                "viacom"
            ],
            "custom": {
                "mood": "0",
                "valence": [],
                "themes": [],
                "genres": []
            },
            "type": "episode",
            "sortTitle": "Masterchef",
            "localisedShortSynopsis": {},
            "releaseYear": 2015,
            "firstAiredAt": "2015-10-14T00:00:00.000Z",
            "duration": "PT1358S",
            "ratings": {
                "MPAA": "R"
            },
            "active": True,
            "memberRefs": [],
            "parentRef": "demo:masterchef",
            "directlyLinkedResourceRef": [
                "demo:genre_contest"
            ],
            "providerRef": "demo:nickelodeon"
        },
        {
            "ref": "demo:resource_three",
            "alternativeIdentifiers": {},
            "owner": "demo",
            "name": "resource_three",
            "title": "News",
            "localisedTitle": {},
            "tags": [
                "viacom"
            ],
            "custom": {
                "mood": "0",
                "valence": [],
                "themes": [],
                "genres": []
            },
            "type": "episode",
            "sortTitle": "News",
            "localisedShortSynopsis": {},
            "releaseYear": 2015,
            "firstAiredAt": "2015-10-14T00:00:00.000Z",
            "duration": "PT1358S",
            "ratings": {
                "MPAA": "R"
            },
            "active": True,
            "memberRefs": [],
            "parentRef": "demo:news",
            "providerRef": "demo:nickelodeon"
        }
    ],
    "linked": {
        "directlyLinkedResources": [
            {
                "ref": "demo:genre_animation",
                "title": "Animation",
                "scheme": "genre",
                "value": "Animation",
                "active": True
            },
            {
                "ref": "demo:genre_contest",
                "title": "Contest",
                "scheme": "genre",
                "value": "Contest",
                "active": True
            }
        ]
    }
}
mock_response_linked_resource_not_in_meta = {
    "meta": {
        "linked": {
            "categories": [
                {
                    "request": "/data/categories/demo:genre_animation?fields=ref%2Ctitle%2CparentRef%2Cscheme%2Cvalue%2Cactive"
                }
            ]
        }
    },
    "pluralResources": [
        {
            "ref": "demo:resource_one",
            "alternativeIdentifiers": {},
            "owner": "demo",
            "name": "resource_one",
            "title": "Bella and the Bulldogs: Personal Foul",
            "localisedTitle": {},
            "tags": [
                "viacom"
            ],
            "custom": {
                "mood": "0",
                "valence": [],
                "themes": [],
                "genres": []
            },
            "type": "episode",
            "sortTitle": "Bella and the Bulldogs: Personal Foul",
            "localisedSortTitle": {},
            "localisedCollateCharacter": {},
            "localisedShortSynopsis": {},
            "releaseYear": 2015,
            "firstAiredAt": "2015-10-14T00:00:00.000Z",
            "duration": "PT1358S",
            "ratings": {
                "MPAA": "R"
            },
            "active": True,
            "memberRefs": [],
            "parentRef": "demo:bella_and_the_bulldogs",
            "directlyLinkedResourceRef": [
                "demo:genre_animation"
            ],
            "providerRef": "demo:nickelodeon"
        }
    ],
    "linked": {
        "resourceNotListedInMeta": [
            {
                "ref": "demo:genre_animation",
                "title": "Animation",
                "scheme": "genre",
                "value": "Animation",
                "active": True
            }
        ]
    }
}

mocked_content_for_validation = {"contents": [
    {
        "ref": "test:609dabcddc229f308f20d01a3d8ff68289950debc14d6ee2cf48e004474512fe",
        "alternativeIdentifiers": {
            "crid": "crid://virginmedia.com/content/MV010463750000"
        },
        "owner": "test",
        "name": "609dabcddc229f308f20d01a3d8ff68289950debc14d6ee2cf48e004474512fe",
        "title": "Naagin Bani Suhagan",
        "type": "movie",
        "sortTitle": "Naagin Bani Suhagan wgfqwregftadsf",
        "collateCharacter": "N",
        "mediumSynopsis": "A woman tries to get revenge on the man who murdered her husband.",
        "releaseYear": 2012,
        "active": True,
        "categoryRefs": [
            "demo:genre-9"
        ]
    },
    {
        "ref": "test:123",
        "owner": "test",
        "name": "123",
        "title": "Naagin Bani Suhagan",
        "type": "movie",
        "sortTitle": "Naagin Bani Suhagan",
        "collateCharacter": "N",
        "mediumSynopsis": "A woman tries to get revenge on the man who murdered her husband.",
        "releaseYear": 2012,
        "active": True,
        "categoryRefs": [
            "demo:genre-9"
        ]
    }
]
}
