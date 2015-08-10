from datetime import datetime
from time import time, sleep
import random
import os
import threading
import logging
import copy
import pdb


#class StateGroup(object):

class State(object):

    def __init__(self, function, *args):
        """Callable State class, contains own logic for Trial to use. If a parameter is a dictionary,
        then the State's function will use the values in the dictionary that correspond to the name of the
        trial that is being run at the time."""

        assert hasattr(function, '__call__'), "state function must be callable!"
        self._function = function

        # Send all params to variable param dictionary (this way, allows both constant and variable parameters)
        self.params_in = args
        self.params_out = None

        self.name = None

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

    def __call__(self):
        """Run the State's associated function with pre-loaded params.  Returns boolean version of result."""
        return self._function(*self.params_out)


class TimerState(State):

    def __init__(self, time_limit):
        """State with built-in timer memory and function.  Doesn't need a function name."""
        super(TimerState, self).__init__(self.timed_out, time_limit)

        self.start_time = None

    def timed_out(self, time_limit):
        """Check if timer has exceeded time_limit yet.  If so, return True."""
        try:
            if time() > self.start_time + time_limit:
                self.start_time = None  # Resets timer for the next trial before returning a value.
                return True
            else:
                return False
        except TypeError:  # Happens when self.start_time isn't a number.
            self.start_time = time()
            return False


class EndState(State):

    def __init__(self):
        """State to be inserted at end of trial.  Does nothing--only the name and type is useful for the trial."""
        super(EndState, self).__init__(self.end_trial)

    def end_trial(self, *args):
        pass


class Trial(object):

    start_time = time()
    trials = []

    def __init__(self, name):
        """Returns a Trial object, a finite state machine moves through each event in a trial.
        ex) myTrial = Trial('MyTrial')
        """
        Trial.trials.append(self)
        self.name = name
        self.states = {}
        self.branches = {}  # experimental logic

        self.start_state = None
        self.current_state = None
        self.last_result = None

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, item):
        return self.states[item]

    def __setitem__(self, key, (state, branch_dict)):
        """Add a new state to the Trial, dictionary-style. Key is name of state, and item is the State."""
        state.name = key
        self.branches[state] = branch_dict
        self.states[key] = state

        if not self.start_state:
            self.start_state = state

    def __iter__(self):
        return self

    def next(self):
        """Iterates through states of the trial.  Returns state result."""

        # Decide if trial should end
        if isinstance(self.current_state, EndState):
            raise StopIteration()  # StopIteration needed for generator function.

        # Set new state based on last_result, and remember last result for logger
        if not self.current_state:
            self.current_state = self.start_state
        else:
            # TODO: Fix the logic that requires this ridiculous line.
            self.current_state = self.states[self.branches[self.current_state][self.last_result]]

        # print self.current_state, self.last_result
        self.last_result = self.current_state()

        # Return result, for experiment logger, which only cares about True results
        return self.last_result  # True or False

    def reset(self):
        self.current_state = None
        self.last_result = None

        for key, state in self.states.items():
            temp_params = []
            for param in state.params_in:
                temp = param
                if isinstance(temp, dict):
                    temp = temp[self.name]
                if hasattr(temp, '__call__'):  # Check if the parameter is callable (i.e. a function)
                    temp = temp()  # Call it to get a new param value for the next trial.
                temp_params.append(temp)
            state.params_out = temp_params

        Trial.start_time = time()

    def copy(self, name):
        assert name != self.name

        new_trial = Trial(name)
        new_trial.start_state = (self.start_state)
        new_trial.states = copy.copy(self.states)
        new_trial.branches = copy.copy(self.branches)
        return new_trial


class Experiment(object):

    start_time = 0  # Experiment Start Time
    trial_num = 0

    def __init__(self, name, trial_list, total_trials, random_fun=random.randint, *random_params):

        assert isinstance(name, str), "Experiment name must be a string!"
        self.name = name

        # Make list of conditions. If only one condition, set Trial Setter to always return 0.
        if not isinstance(trial_list, list):
            trial_list = [trial_list]
        if len(trial_list) == 1 or random_fun == random.randint:
            random_params = (0, len(trial_list) - 1)
        self.conditions = trial_list

        # Initialize first Trial and Trial Selectors
        self.numTrials = total_trials
        self.random_fun = random_fun
        self.random_params = random_params

    def __iter__(self):
        return self

    def next(self):
        """Get next trial, using an arbitrary randomizer function."""

        if Experiment.trial_num == self.numTrials:
            raise StopIteration
        else:
            # Select the new condition, based on the int randomizer function.
            cond_idx = self.random_fun(*self.random_params)
            trial = self.conditions[cond_idx]

            # Prepare the new trial and return it.
            Experiment.trial_num += 1  # Increase the trial counter and timer.
            trial.reset()
            return trial


class ExperimentThread(threading.Thread):

    def __init__(self, experiment, tracker=None, log=True, daemon=True, directory=os.path.join(os.getcwd(),'Logs')):
        """Controls the experiment and polls it to advance to the next state.
        Also calls logging methods and initializes Logger."""

        super(ExperimentThread, self).__init__()
        self.setDaemon(daemon)

        self._stop = threading.Event()
        self.experiment = experiment
        self.tracker = tracker

        if log:
            self.logdata = {'Exp. Time': 0, 'Trial Num': 0, 'Trial Type': '', 'Trial Time': 0, 'Event': '', 'Event Data': 0}
            if not os.path.isdir(directory):
                os.mkdir(directory)
            file_name = os.path.join(directory, experiment.name + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.explog')
            with open(file_name,'wb') as log_file:
                log_file.write('Experiment: ' + self.experiment.name + '\nStarted on: {0}\n\n'.format(datetime.now()))
                log_file.write('\t'.join(self.logdata.keys()) + '\n')

            logging.basicConfig(filename=file_name, level=logging.DEBUG,
                                format='%(' + ')s\t%('.join(self.logdata.keys()) + ')s')  # uses keys from self.logdata

            # Console Logger, as well (for minor messages, like end of trial, or beginning the experiment)
            self.console_log = logging.Logger('exp_console', level=logging.DEBUG)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter('%(message)s'))
            self.console_log.addHandler(stream_handler)

    def run(self):

        Experiment.start_time = time()
        self.console_log.debug('Running Experiment...')
        for trial in self.experiment:
            for result in trial:

                sleep(.00001)  # Hand over control back to GIL between loops, so python can do other things in the meantime!

                if (result is True or result is None):  # Log event if state fun returns True
                    if self.tracker:
                        self.logdata['Tracker Frame Num.'] = self.tracker.frame
                    now = time()
                    sf = '{0:10.3f}'
                    self.logdata['Exp. Time'] = sf.format(now - Experiment.start_time)
                    self.logdata['Trial Type'] = trial
                    self.logdata['Trial Num'] = Experiment.trial_num
                    self.logdata['Trial Time'] = sf.format(now - Trial.start_time)
                    self.logdata['Event'] = trial.current_state
                    self.logdata['Event Data'] = trial.current_state.params_out
                    logging.debug('', extra=self.logdata)

            self.console_log.debug('End of Trial {0}'.format(Experiment.trial_num))

        self.console_log.debug('End of Experiment')


