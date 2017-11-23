import codecs
import os
import time
import shlex
import signal

from winpty import PtyProcess

from .exceptions import ExceptionPexpect, TIMEOUT
from .spawnbase import SpawnBase
from .utils import select_ignore_interrupts


class spawn(SpawnBase):
    '''This is the main class interface for Pexpect. Use this class to start
    and control child applications. '''

    def __init__(self, command, args=[], timeout=30, maxread=2000, echo=False,
                 searchwindowsize=None, logfile=None, cwd=None, env=None,
                 encoding=None, codec_errors='strict', dimensions=None):
        '''This is the constructor. The command parameter may be a string that
        includes a command and any arguments to the command. For example::

            child = spawn('/usr/bin/ftp')
            child = spawn('/usr/bin/ssh user@example.com')
            child = spawn('ls -latr /tmp')

        You may also construct it with a list of arguments like so::

            child = spawn('/usr/bin/ftp', [])
            child = spawn('/usr/bin/ssh', ['user@example.com'])
            child = spawn('ls', ['-latr', '/tmp'])

        After this the child application will be created and will be ready to
        talk to. For normal use, see expect() and send() and sendline().

        Remember that Pexpect does NOT interpret shell meta characters such as
        redirect, pipe, or wild cards (``>``, ``|``, or ``*``). This is a
        common mistake.  If you want to run a command and pipe it through
        another command then you must also start a shell. For example::

            child = spawn('/bin/bash -c "ls -l | grep LOG > logs.txt"')
            child.expect(pexpect.EOF)

        The second form of spawn (where you pass a list of arguments) is useful
        in situations where you wish to spawn a command and pass it its own
        argument list. This can make syntax more clear. For example, the
        following is equivalent to the previous example::

            shell_cmd = 'ls -l | grep LOG > logs.txt'
            child = spawn('/bin/bash', ['-c', shell_cmd])
            child.expect(pexpect.EOF)

        The maxread attribute sets the read buffer size. This is maximum number
        of bytes that Pexpect will try to read from a TTY at one time. Setting
        the maxread size to 1 will turn off buffering. Setting the maxread
        value higher may help performance in cases where large amounts of
        output are read back from the child. This feature is useful in
        conjunction with searchwindowsize.

        When the keyword argument *searchwindowsize* is None (default), the
        full buffer is searched at each iteration of receiving incoming data.
        The default number of bytes scanned at each iteration is very large
        and may be reduced to collaterally reduce search cost.  After
        :meth:`~.expect` returns, the full buffer attribute remains up to
        size *maxread* irrespective of *searchwindowsize* value.

        When the keyword argument ``timeout`` is specified as a number,
        (default: *30*), then :class:`TIMEOUT` will be raised after the value
        specified has elapsed, in seconds, for any of the :meth:`~.expect`
        family of method calls.  When None, TIMEOUT will not be raised, and
        :meth:`~.expect` may block indefinitely until match.


        The logfile member turns on or off logging. All input and output will
        be copied to the given file object. Set logfile to None to stop
        logging. This is the default. Set logfile to sys.stdout to echo
        everything to standard output. The logfile is flushed after each write.

        Example log input and output to a file::

            child = spawn('some_command')
            fout = open('mylog.txt','wb')
            child.logfile = fout

        Example log to stdout::

            child = spawn('some_command')
            child.logfile = sys.stdout

        The logfile_read and logfile_send members can be used to separately log
        the input from the child and output sent to the child. Sometimes you
        don't want to see everything you write to the child. You only want to
        log what the child sends back. For example::

            child = spawn('some_command')
            child.logfile_read = sys.stdout

        To separately log output sent to the child use logfile_send::

            child.logfile_send = fout

        The delaybeforesend helps overcome a weird behavior that many users
        were experiencing. The typical problem was that a user would expect() a
        "Password:" prompt and then immediately call sendline() to send the
        password. The user would then see that their password was echoed back
        to them. Passwords don't normally echo. The problem is caused by the
        fact that most applications print out the "Password" prompt and then
        turn off stdin echo, but if you send your password before the
        application turned off echo, then you get your password echoed.
        Normally this wouldn't be a problem when interacting with a human at a
        real keyboard. If you introduce a slight delay just before writing then
        this seems to clear up the problem. This was such a common problem for
        many users that I decided that the default pexpect behavior should be
        to sleep just before writing to the child application. 1/20th of a
        second (50 ms) seems to be enough to clear up the problem. You can set
        delaybeforesend to None to return to the old behavior.

        Note that spawn is clever about finding commands on your path.
        It uses the same logic that "which" uses to find executables.

        If you wish to get the exit status of the child you must call the
        close() method. The exit status of the child will be stored
        in self.exitstatus::

            child = spawn('some_command')
            child.close()
            print(child.exitstatus)

        The dimensions attribute specifies the size of the pseudo-terminal as
        seen by the subprocess, and is specified as a two-entry tuple (rows,
        columns). If this is unspecified, the defaults in winpty will apply.
        '''
        super(spawn, self).__init__(timeout=timeout, maxread=maxread, searchwindowsize=searchwindowsize,
                                    logfile=logfile, encoding=encoding, codec_errors=codec_errors)
        self.cwd = cwd
        self.env = env
        self._echo = echo
        if self.encoding is None:
            self._encoder = codecs.getincrementalencoder('utf-8')(codec_errors)
            self.linesep = self.linesep.decode('utf-8')
        if command is None:
            self.command = None
            self.args = None
            self.name = '<pexpect factory incomplete>'
        else:
            self._spawn(command, args, dimensions)

    def __str__(self):
        '''This returns a human-readable string that represents the state of
        the object. '''

        s = []
        s.append(repr(self))
        s.append('command: ' + str(self.command))
        s.append('args: %r' % (self.args,))
        s.append('buffer (last 100 chars): %r' % (
                self.buffer[-100:] if self.buffer else self.buffer,))
        s.append('before (last 100 chars): %r' % (
                self.before[-100:] if self.before else self.before,))
        s.append('after: %r' % (self.after,))
        s.append('match: %r' % (self.match,))
        s.append('match_index: ' + str(self.match_index))
        s.append('exitstatus: ' + str(self.exitstatus))
        if hasattr(self, 'ptyproc'):
            s.append('flag_eof: ' + str(self.flag_eof))
        s.append('pid: ' + str(self.pid))
        s.append('child_fd: ' + str(self.child_fd))
        s.append('closed: ' + str(self.closed))
        s.append('timeout: ' + str(self.timeout))
        s.append('delimiter: ' + str(self.delimiter))
        s.append('logfile: ' + str(self.logfile))
        s.append('logfile_read: ' + str(self.logfile_read))
        s.append('logfile_send: ' + str(self.logfile_send))
        s.append('maxread: ' + str(self.maxread))
        s.append('ignorecase: ' + str(self.ignorecase))
        s.append('searchwindowsize: ' + str(self.searchwindowsize))
        s.append('delaybeforesend: ' + str(self.delaybeforesend))
        s.append('delayafterclose: ' + str(self.delayafterclose))
        s.append('delayafterterminate: ' + str(self.delayafterterminate))
        return '\n'.join(s)

    def _spawn(self, command, args=[], dimensions=None):
        '''This starts the given command in a child process. This is called by __init__.
        If args is empty then command will be parsed (split on spaces) and args will be
        set to parsed arguments. '''

        # The pid and child_fd of this object get set by this method.
        # Note that it is difficult for this method to fail.
        # You cannot detect if the child process cannot start.
        # So the only way you can tell if the child process started
        # or not is to try to read from the file descriptor. If you get
        # EOF immediately then it means that the child is already dead.
        # That may not necessarily be bad because you may have spawned a child
        # that performs some task; creates no stdout output; and then dies.

        # If command is an int type then it may represent a file descriptor.
        if isinstance(command, type(0)):
            raise ExceptionPexpect('Command is an int type. ' +
                    'If this is a file descriptor then maybe you want to ' +
                    'use fdpexpect.fdspawn which takes an existing ' +
                    'file descriptor instead of a command string.')

        if not isinstance(args, type([])):
            raise TypeError('The argument, args, must be a list.')

        assert self.pid is None, 'The pid member must be None.'
        assert command is not None, 'The command member must not be None.'

        kwargs = dict()
        if dimensions is not None:
            kwargs['dimensions'] = dimensions

        command = shlex.split(command, posix=False)
        args = command + args

        self.ptyproc = proc = PtyProcess.spawn(args, env=self.env,
                                     cwd=self.cwd, **kwargs)

        self.args = proc.argv
        self.command = self.args[0]
        self.name = '<' + ' '.join(self.args) + '>'
        self.pid = proc.pid
        self.child_fd = proc.fd

        self.terminated = False
        self.closed = False

    def close(self, force=True):
        '''This closes the connection with the child application. Note that
        calling close() more than once is valid. This emulates standard Python
        behavior with files. Set force to True if you want to make sure that
        the child is terminated (SIGKILL is sent if the child ignores SIGINT). '''

        self.flush()
        self.ptyproc.close(force=force)
        self.isalive()  # Update exit status from ptyproc
        self.child_fd = -1

    def isatty(self):
        '''This returns True if the file descriptor is open and connected to a
        tty(-like) device, else False.'''

        return self.ptyproc.isatty()

    def read_nonblocking(self, size=1, timeout=-1):
        '''This reads at most size characters from the child application. It
        includes a timeout. If the read does not complete within the timeout
        period then a TIMEOUT exception is raised. If the end of file is read
        then an EOF exception will be raised.  If a logfile is specified, a
        copy is written to that log.

        If timeout is None then the read may block indefinitely.
        If timeout is -1 then the self.timeout value is used. If timeout is 0
        then the child is polled and if there is no data immediately ready
        then this will raise a TIMEOUT exception.

        The timeout refers only to the amount of time to read at least one
        character. This is not affected by the 'size' parameter, so if you call
        read_nonblocking(size=100, timeout=30) and only one character is
        available right away then one character will be returned immediately.
        It will not wait for 30 seconds for another 99 characters to come in.

        It uses select.select() to implement the timeout. '''

        if self.closed:
            raise ValueError('I/O operation on closed file.')

        if timeout == -1:
            timeout = self.timeout

        r, w, e = select_ignore_interrupts([self.child_fd], [], [], timeout)

        if not r:
            raise TIMEOUT('Timeout exceeded.')

        if self.child_fd in r:
            s = self.ptyproc.read(size)
            s = self._encoder.encode(s, final=False)
            self._log(s, 'read')
            s = self._decoder.decode(s, final=False)
            return s

        raise ExceptionPexpect('Reached an unexpected state.')  # pragma: no cover

    def write(self, s):
        '''This is similar to send() except that there is no return value.
        '''

        self.send(s)

    def writelines(self, sequence):
        '''This calls write() for each element in the sequence. The sequence
        can be any iterable object producing strings, typically a list of
        strings. This does not add line separators. There is no return value.
        '''

        for s in sequence:
            self.write(s)

    def send(self, s):
        '''Sends string ``s`` to the child process, returning the number of
        bytes written. If a logfile is specified, a copy is written to that
        log.
        '''

        if self.delaybeforesend is not None:
            time.sleep(self.delaybeforesend)

        s = self._coerce_send_string(s)
        self._log(s, 'send')
        return self.ptyproc.write(s)

    def _coerce_send_string(self, s):
        if isinstance(s, bytes):
            s = s.decode('utf-8')
        return s

    def sendline(self, s=''):
        '''Wraps send(), sending string ``s`` to child process, with
        ``os.linesep`` automatically appended. Returns number of bytes
        written.  Only a limited number of bytes may be sent for each
        line in the default terminal mode, see docstring of :meth:`send`.
        '''
        s = self._coerce_send_string(s)
        return self.send(s + self.linesep)

    def _log_control(self, s):
        """Write control characters to the appropriate log files"""
        if self.encoding is not None:
            s = s.decode(self.encoding, 'replace')
        self._log(s, 'send')

    def sendcontrol(self, char):
        '''Helper method that wraps send() with mnemonic access for sending control
        character to the child (such as Ctrl-C or Ctrl-D).  For example, to send
        Ctrl-G (ASCII 7, bell, '\a')::

            child.sendcontrol('g')

        See also, sendintr() and sendeof().
        '''
        n, byte = self.ptyproc.sendcontrol(char)
        self._log_control(byte)
        return n

    def sendeof(self):
        '''This sends an EOF to the child. This sends a character which causes
        the pending parent output buffer to be sent to the waiting child
        program without waiting for end-of-line. If it is the first character
        of the line, the read() in the user program returns 0, which signifies
        end-of-file. This means to work as expected a sendeof() has to be
        called at the beginning of a line. This method does not send a newline.
        It is the responsibility of the caller to ensure the eof is sent at the
        beginning of a line. '''

        n, byte = self.ptyproc.sendeof()
        self._log_control(byte)

    def sendintr(self):
        '''This sends a SIGINT to the child. It does not require
        the SIGINT to be the first character on a line. '''

        n, byte = self.ptyproc.sendintr()
        self._log_control(byte)

    def waitnoecho(self, timeout=-1):
        '''This is a stub for compatibility with the pty versio
        '''
        return

    def getecho(self):
        '''This is a stub for compatibility with the pty version '''
        return self._echo

    def setecho(self, state):
        """This is a stub for compatibility with the pty version
        """
        self._echo = state

    @property
    def flag_eof(self):
        return self.ptyproc.flag_eof

    @flag_eof.setter
    def flag_eof(self, value):
        self.ptyproc.flag_eof = value

    def eof(self):
        '''This returns True if the EOF exception was ever raised.
        '''
        return self.flag_eof

    def terminate(self, force=False):
        '''This forces a child process to terminate. It starts nicely with
        SIGINT. If "force" is True then moves onto SIGKILL. This
        returns True if the child was terminated. This returns False if the
        child could not be terminated. '''

        if not self.isalive():
            return True
        try:
            self.kill(signal.SIGINT)
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            if force:
                self.kill(signal.SIGKILL)
                time.sleep(self.delayafterterminate)
                if not self.isalive():
                    return True
                else:
                    return False
            return False
        except OSError:
            # I think there are kernel timing issues that sometimes cause
            # this to happen. I think isalive() reports True, but the
            # process is dead to the kernel.
            # Make one last attempt to see if the kernel is up to date.
            time.sleep(self.delayafterterminate)
            if not self.isalive():
                return True
            else:
                return False

    def wait(self):
        '''This waits until the child exits. This is a blocking call. This will
        not read any data from the child, so this will block forever if the
        child has unread output and has terminated. In other words, the child
        may have printed output then called exit(), but, the child is
        technically still alive until its output is read by the parent.

        This method is non-blocking if :meth:`wait` has already been called
        previously or :meth:`isalive` method returns False.  It simply returns
        the previously determined exit status.
        '''

        ptyproc = self.ptyproc
        exitstatus = ptyproc.wait()
        self.exitstatus = ptyproc.exitstatus
        self.terminated = True

        return exitstatus

    def isalive(self):
        '''This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exitstatus of the child. This returns True if the child
        process appears to be running or False if not. It can take literally
        SECONDS for Solaris to return the right status. '''

        ptyproc = self.ptyproc
        alive = ptyproc.isalive()

        if not alive:
            self.exitstatus = ptyproc.exitstatus
            self.terminated = True

        return alive

    def kill(self, sig):
        '''This sends the given signal to the child application.  It does not
        necessarily kill the child unless you send the right signal. '''

        # Same as os.kill, but the pid is given for you.
        if self.isalive():
            os.kill(self.pid, sig)

    def getwinsize(self):
        '''This returns the terminal window size of the child tty. The return
        value is a tuple of (rows, cols). '''
        return self.ptyproc.getwinsize()

    def setwinsize(self, rows, cols):
        '''This sets the terminal window size of the child tty. This will cause
        a SIGWINCH signal to be sent to the child. This does not change the
        physical window size. It changes the size reported to TTY-aware
        applications like vi or curses -- applications that respond to the
        SIGWINCH signal. '''
        return self.ptyproc.setwinsize(rows, cols)


def spawnu(*args, **kwargs):
    """Deprecated: pass encoding to spawn() instead."""
    kwargs.setdefault('encoding', 'utf-8')
    return spawn(*args, **kwargs)
