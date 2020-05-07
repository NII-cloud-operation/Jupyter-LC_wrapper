import asyncio

from jupyter_client.session import Session
from jupyter_client.ioloop import AsyncIOLoopKernelManager


class AsyncLCWrapperKernelManager(AsyncIOLoopKernelManager):
    """Async Kernel manager for LC_wrapper kernel"""

    async def start_kernel(self, **kw):
        await super(AsyncLCWrapperKernelManager, self).start_kernel(**kw)

        self.start_watching_execution_state()

    def start_watching_execution_state(self):
        self._executing = False

        self._watch_state_stream = self.connect_iopub()
        session = Session(
            config=self.session.config,
            key=self.session.key,
        )

        def record_state(msg_list):
            idents, fed_msg_list = session.feed_identities(msg_list)
            msg = session.deserialize(fed_msg_list)

            msg_type = msg['header']['msg_type']
            if msg_type == 'status':
                execution_state = msg['content']['execution_state']
                self.log.debug("kernel_state : %s (%s)", msg_type, execution_state)
                parent_msg_type = msg['parent_header'].get('msg_type', '')
                parent_msg_id = msg['parent_header'].get('msg_id', '')
                if parent_msg_type == 'execute_request':
                    if execution_state == 'busy':
                        self.log.debug("start execution: msg_id=%s", parent_msg_id)
                        self._executing = True
                    elif execution_state == 'idle':
                        self.log.debug("end execution: msg_id=%s", parent_msg_id)
                        self._executing = False

        self._watch_state_stream.on_recv(record_state)

    async def _wait_for_idle(self):
        waittime = 5.0
        pollinterval = 0.1
        for i in range(int(waittime/pollinterval)):
            self.log.debug("waiting for kernel to become idle")
            if self._executing:
                await asyncio.sleep(pollinterval)
            else:
                self.log.debug("kernel become idle")
                break

    async def shutdown_kernel(self, now=False, restart=False):
        # Stop monitoring for restarting while we shutdown.
        self.stop_restarter()

        self.log.debug("Interrupting the wrapper kernel and its subprocesses")
        await self.interrupt_kernel()
        await self._wait_for_idle()

        if self._watch_state_stream:
            self._watch_state_stream.close()
            self._watch_state_stream = None

        if now:
            await self._kill_kernel()
        else:
            self.request_shutdown(restart=restart)
            # Don't send any additional kernel kill messages immediately, to give
            # the kernel a chance to properly execute shutdown actions. Wait for at
            # most 1s, checking every 0.1s.
            await self.finish_shutdown()

        self.cleanup(connection_file=not restart)

