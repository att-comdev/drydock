# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Generic testing for the orchestrator
#

import helm_drydock.orchestrator as orch
import helm_drydock.enum as enum
import helm_drydock.statemgmt as statemgmt
import helm_drydock.model.task as task
import helm_drydock.drivers as drivers
import threading
import time

class TestClass(object):

    def test_task_complete(self):
        state_mgr = statemgmt.DesignState()
        orchestrator = orch.Orchestrator(state_manager=state_mgr)
        orch_task = orchestrator.create_task(task.OrchestratorTask,
                                             site='default',
                                             action=enum.OrchestratorAction.Noop)

        orchestrator.execute_task(orch_task.get_id())

        orch_task = state_mgr.get_task(orch_task.get_id())

        assert orch_task.get_status() == enum.TaskStatus.Complete

        for t_id in orch_task.subtasks:
            t = state_mgr.get_task(t_id)
            assert t.get_status() == enum.TaskStatus.Complete

    def test_task_termination(self):
        state_mgr = statemgmt.DesignState()
        orchestrator = orch.Orchestrator(state_manager=state_mgr)
        orch_task = orchestrator.create_task(task.OrchestratorTask,
                                             site='default',
                                             action=enum.OrchestratorAction.Noop)

        orch_thread = threading.Thread(target=orchestrator.execute_task,
                                       args=(orch_task.get_id(),))
        orch_thread.start()

        time.sleep(1)
        orchestrator.terminate_task(orch_task.get_id())

        while orch_thread.is_alive():
            time.sleep(1)

        orch_task = state_mgr.get_task(orch_task.get_id())
        assert orch_task.get_status() == enum.TaskStatus.Terminated

        for t_id in orch_task.subtasks:
            t = state_mgr.get_task(t_id)
            assert t.get_status() == enum.TaskStatus.Terminated