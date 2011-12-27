from twisted.application import service

class SamplePlugin(service.Service):
    def cmd_foo(self, command, arguments):
        pass
