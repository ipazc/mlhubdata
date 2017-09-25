#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from mldatahub.config.config import global_config
from mldatahub.factory.dataset_element_factory import DatasetElementFactory

global_config.set_local_storage_uri("examples/tmp_folder")
global_config.set_session_uri("mongodb://localhost:27017/unittests")
from werkzeug.exceptions import Unauthorized, BadRequest
from mldatahub.config.privileges import Privileges
import unittest
from mldatahub.odm.dataset_dao import DatasetDAO, DatasetCommentDAO, DatasetElementDAO, DatasetElementCommentDAO, \
    taken_url_prefixes
from mldatahub.odm.token_dao import TokenDAO


__author__ = 'Iván de Paz Centeno'

local_storage = global_config.get_local_storage()

class TestDatasetElementFactory(unittest.TestCase):

    def setUp(self):
        self.session = global_config.get_session()
        DatasetDAO.query.remove()
        DatasetCommentDAO.query.remove()
        DatasetElementDAO.query.remove()
        DatasetElementCommentDAO.query.remove()
        TokenDAO.query.remove()
        taken_url_prefixes.clear()

    def test_dataset_element_creation(self):
        """
        Factory can create dataset's elements
        """
        anonymous = TokenDAO("Anonymous", 1, 1, "anonymous")

        creator = TokenDAO("normal user privileged with link", 1, 1, "user1",
                           privileges=Privileges.CREATE_DATASET + Privileges.ADD_ELEMENTS
                           )
        creator2 = TokenDAO("normal user unprivileged", 1, 1, "user1",
                           privileges=Privileges.CREATE_DATASET
                           )
        admin = TokenDAO("admin user", 1, 1, "admin", privileges=Privileges.ADMIN_CREATE_TOKEN + Privileges.ADMIN_EDIT_TOKEN + Privileges.ADMIN_DESTROY_TOKEN)

        dataset = DatasetDAO("user1/dataset1", "example_dataset", "dataset for testing purposes", "none", tags=["example", "0"])
        dataset2 = DatasetDAO("user1/dataset2", "example_dataset2", "dataset2 for testing purposes", "none", tags=["example", "1"])

        self.session.flush()

        creator = creator.link_dataset(dataset)
        creator2 = creator2.link_dataset(dataset)

        # Creator can create elements into the dataset
        element = DatasetElementFactory(creator, dataset).create_element(title="New element", description="Description unknown",
                                                               tags=["example_tag"], content=b"hello")

        self.assertEqual(element.tags, ["example_tag"])

        content = local_storage.get_file_content(element.file_ref_id)
        self.assertEqual(content, b"hello")
        self.session.flush()
        # Creator can't create elements referencing existing files directly (Exploit fix)
        with self.assertRaises(Unauthorized) as ex:
            element = DatasetElementFactory(creator, dataset).create_element(title="New element2",
                                                                             description="Description unknown2",
                                                                             tags=["example_tag"],
                                                                             file_ref_id=element.file_ref_id)

        # Creator can't create elements on other's datasets if not linked with them
        with self.assertRaises(Unauthorized) as ex:
            element = DatasetElementFactory(creator, dataset2).create_element(title="New element2",
                                                                              description="Description unknown2",
                                                                              tags=["example_tag"], content=b"hello2")

        # Anonymous can't create elements
        with self.assertRaises(Unauthorized) as ex:
            element = DatasetElementFactory(anonymous, dataset).create_element(title="New element3", description="Description unknown",
                                                               tags=["example_tag"], content=b"hello3")

        # Creator2, even linked to the dataset, can't create elements as it is not privileged
        with self.assertRaises(Unauthorized) as ex:
            element = DatasetElementFactory(creator2, dataset).create_element(title="New element4",
                                                                              description="Description unknown4",
                                                                              tags=["example_tag"], content=b"hello4")

        # Admin can do any of the previous actions.
        element = DatasetElementFactory(admin, dataset).create_element(title="New element5",
                                                                          description="Description unknown5",
                                                                          tags=["example_tag"], content=b"hello5")
        self.session.flush_all()
        self.session.refresh(dataset)

        dataset = DatasetDAO.query.get(_id=dataset._id)
        self.assertEqual(element.dataset_id, dataset._id)
        self.assertEqual(len(dataset.elements), 2)

        new_element = DatasetElementFactory(admin, dataset2).create_element(title="New element6",
                                                                  description="Description unknown5",
                                                                  tags=["example_tag"], file_ref_id=element.file_ref_id)

        self.assertEqual(element.file_ref_id, new_element.file_ref_id)

    def test_dataset_element_removal(self):
        """
        Factory can remove elements from datasets.
        """
        anonymous = TokenDAO("Anonymous", 1, 1, "anonymous")

        destructor = TokenDAO("normal user privileged with link", 1, 1, "user1",
                           privileges=Privileges.DESTROY_DATASET + Privileges.DESTROY_ELEMENTS
                           )
        destructor2 = TokenDAO("normal user unprivileged", 1, 1, "user1",
                           privileges=Privileges.DESTROY_DATASET
                           )
        admin = TokenDAO("admin user", 1, 1, "admin", privileges=Privileges.ADMIN_CREATE_TOKEN + Privileges.ADMIN_EDIT_TOKEN + Privileges.ADMIN_DESTROY_TOKEN)

        dataset = DatasetDAO("user1/dataset1", "example_dataset", "dataset for testing purposes", "none", tags=["example", "0"])
        dataset2 = DatasetDAO("user1/dataset2", "example_dataset2", "dataset2 for testing purposes", "none", tags=["example", "1"])

        self.session.flush()

        destructor = destructor.link_dataset(dataset)
        destructor2 = destructor2.link_dataset(dataset2)

        file_id1 = local_storage.put_file_content(b"content1")
        file_id2 = local_storage.put_file_content(b"content2")

        element  = DatasetElementDAO("example1", "none", file_id1, dataset=dataset)
        element2 = DatasetElementDAO("example2", "none", file_id1, dataset=dataset)
        element3 = DatasetElementDAO("example3", "none", file_id2, dataset=dataset2)

        self.session.flush()
        dataset = dataset.update()
        dataset2 = dataset2.update()

        self.assertEqual(len(dataset.elements), 2)
        self.assertEqual(len(dataset2.elements), 1)

        # Destructor can not destroy elements from a dataset that is not linked to
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(destructor, dataset2).destroy_element(element._id)

        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(destructor, dataset2).destroy_element(element2._id)

        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(destructor, dataset2).destroy_element(element3._id)

        # Destructor can not destroy elements if they exist but are not inside his dataset
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(destructor, dataset).destroy_element(element3._id)

        # Destructor can not destroy elements if they don't exist
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(destructor, dataset).destroy_element("randomID")

        # Destructor can destroy elements if they exist and are  inside his dataset
        DatasetElementFactory(destructor, dataset).destroy_element(element._id)

        # Even though element is destroyed, file referenced should still exist
        self.assertEqual(local_storage.get_file_content(file_id1), b"content1")

        dataset = dataset.update()

        self.assertEqual(len(dataset.elements), 1)

        # Admin can remove elements form any source
        DatasetElementFactory(admin, dataset).destroy_element(element2._id)
        DatasetElementFactory(admin, dataset2).destroy_element(element3._id)

        self.session.flush()

        dataset = dataset.update()
        dataset2 = dataset2.update()

        self.assertEqual(len(dataset.elements), 0)
        self.assertEqual(len(dataset2.elements), 0)

    def test_dataset_element_edit(self):
        """
        Factory can edit elements from datasets.
        """
        editor = TokenDAO("normal user privileged with link", 1, 1, "user1",
                           privileges=Privileges.EDIT_DATASET + Privileges.EDIT_ELEMENTS
                           )
        editor2 = TokenDAO("normal user unprivileged", 1, 1, "user1",
                           privileges=Privileges.EDIT_DATASET
                           )
        admin = TokenDAO("admin user", 1, 1, "admin", privileges=Privileges.ADMIN_CREATE_TOKEN + Privileges.ADMIN_EDIT_TOKEN + Privileges.ADMIN_DESTROY_TOKEN)

        dataset = DatasetDAO("user1/dataset1", "example_dataset", "dataset for testing purposes", "none", tags=["example", "0"])
        dataset2 = DatasetDAO("user1/dataset2", "example_dataset2", "dataset2 for testing purposes", "none", tags=["example", "1"])

        self.session.flush()

        editor = editor.link_dataset(dataset)
        editor2 = editor2.link_dataset(dataset2)

        file_id1 = local_storage.put_file_content(b"content1")
        file_id2 = local_storage.put_file_content(b"content2")

        element  = DatasetElementDAO("example1", "none", file_id1, dataset=dataset)
        element2 = DatasetElementDAO("example2", "none", file_id1, dataset=dataset)
        element3 = DatasetElementDAO("example3", "none", file_id2, dataset=dataset2)

        self.session.flush()
        dataset = dataset.update()
        dataset2 = dataset2.update()

        self.assertEqual(len(dataset.elements), 2)
        self.assertEqual(len(dataset2.elements), 1)

        # editor can not edit elements from a dataset that is not linked to
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset2).edit_element(element._id, title="asd")

        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset2).edit_element(element2._id, title="asd2")

        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset2).edit_element(element3._id, title="asd3")

        # editor can not edit elements if they exist but are not inside his dataset
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset).edit_element(element3._id, title="asd4")

        # editor can not edit elements if they don't exist
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset).edit_element("randomID", title="asd5")

        # Editor can edit elements if they exist and are inside his dataset
        DatasetElementFactory(editor, dataset).edit_element(element._id, title="asd6")

        self.session.flush()

        dataset = dataset.update()
        element = element.update()

        # Editor can not change references to files
        with self.assertRaises(Unauthorized) as ex:
            DatasetElementFactory(editor, dataset).edit_element(element._id, file_ref_id="other_reference")

        # BUT he can change the content
        DatasetElementFactory(editor, dataset).edit_element(element._id, content=b"other_content")

        element = element.update()
        self.assertEqual(local_storage.get_file_content(element.file_ref_id), b"other_content")

        # Admin can do whatever he wants
        DatasetElementFactory(admin, dataset).edit_element(element2._id, title="changed by admin")
        element2 = element2.update()
        self.assertEqual(element2.title, "changed by admin")

        DatasetElementFactory(admin, dataset2).edit_element(element3._id, file_ref_id=element.file_ref_id)

        element3 = element3.update()
        self.assertEqual(local_storage.get_file_content(element3.file_ref_id),
                         local_storage.get_file_content(element.file_ref_id))

        self.session.flush()


    def tearDown(self):
        DatasetDAO.query.remove()
        DatasetCommentDAO.query.remove()
        DatasetElementDAO.query.remove()
        DatasetElementCommentDAO.query.remove()
        TokenDAO.query.remove()
        taken_url_prefixes.clear()

    @classmethod
    def tearDownClass(cls):
        local_storage.delete()

if __name__ == '__main__':
    unittest.main()
