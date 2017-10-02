#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# MLDataHub
# Copyright (C) 2017 Iván de Paz Centeno <ipazc@unileon.es>.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 3
# of the License or (at your option) any later version of
# the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

import json
import os
from multiprocessing import Lock
import shutil
import uuid
from mldatahub.config.config import global_config, now
from mldatahub.storage.generic_storage import GenericStorage

__author__ = 'Iván de Paz Centeno'


SAVE_INTERVAL = global_config.get_save_interval()


class LocalStorage(GenericStorage):
    def __init__(self, root_key):
        super().__init__(root_key)

        self.lock = Lock()

        if not os.path.exists(root_key):
            os.makedirs(root_key)

        # Initializing...
        try:
            with open(global_config.get_storage_cache_file()) as f:
                files_descr = json.load(f)
        except FileNotFoundError as ex:
            files_descr = {'closed': False, 'files': []}

        if not files_descr['closed']:
            print("Storage wasn't closed gracefully. It must be reloaded and it may take several minutes...")
            files_descr = {'closed': True, 'files': os.listdir(root_key)}

        with open(global_config.get_storage_cache_file(), "w") as f:
            json.dump(files_descr, f, indent=4)

        self.files_list = set(files_descr['files'])

        self.last_saved_check = now()

    def _save_file_list(self, closed=False):
        files_descr = {'closed': closed, 'files': list(self.files_list)}
        with open(global_config.get_storage_cache_file(), "w") as f:
            json.dump(files_descr, f, indent=4)
        self.last_saved_check = now()

    def put_file_content(self, content_bytes, file_id=None):
        if file_id is None:
            file_id = self._generate_token()

        with open(os.path.join(self.root_key, file_id), "wb") as f:
            f.write(content_bytes)

        with self.lock:
            self.files_list.add(file_id)

        return file_id

    def _generate_token(self):
        id = str(uuid.uuid4().hex)
        while os.path.exists(os.path.join(self.root_key, id)):
            id = str(uuid.uuid4().hex)

        return id

    def get_file_content(self, file_id):
        try:
            with open(os.path.join(self.root_key, file_id), "rb") as f:
                content_bytes = f.read()
        except FileNotFoundError as ex:
            content_bytes = b""

        return content_bytes

    def delete_file_content(self, file_id):
        if file_id in self.files_list:
            self.files_list.remove(file_id)

        if os.path.exists(os.path.join(self.root_key, file_id)):
            os.remove(os.path.join(self.root_key, file_id))
        else:
            raise FileNotFoundError()

    def __iter__(self):
        files_list = self.files_list

        for f in files_list:
            yield f

    def delete(self):
        if os.path.exists(self.root_key):
            shutil.rmtree(self.root_key)
        self.files_list = set()
        self._save_file_list()

    def heart_pulse(self):
        """
        Performs check to save the storage list into a file if required.
        Should by called by an external timer.
        :return:
        """
        if (now() - self.last_saved_check).total_seconds() > SAVE_INTERVAL:
            self._save_file_list()

    def close(self):
        self._save_file_list(closed=True)
