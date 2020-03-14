# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.


from tests.compat import mock

from airflow.contrib.secrets.aws_ssm import AwsSsmSecretsBackend


@mock.patch("airflow.contrib.secrets.aws_ssm.AwsSsmSecretsBackend.get_conn_uri")
def test_aws_ssm_get_connections(mock_get_uri):
    mock_get_uri.side_effect = ["scheme://user:pass@host:100"]
    conn_list = AwsSsmSecretsBackend().get_connections("fake_conn")
    conn = conn_list[0]
    assert conn.host == 'host'
