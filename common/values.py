class TerminationReasons:
    ILLEGAL_SYSCALL = 'IS'
    ENOMEM =          'EM'
    UNKNOWN_KILL =    'UK'
    UNKNOWN_SIGNAL =  'US'
    UNEXP_CONT =      'UC'
    SABOTAGE =        'CS'
    XCPUTIME =        'XT'
    SECCOMP =         'SP'  # shouldn't really happen unless there is a bug.

