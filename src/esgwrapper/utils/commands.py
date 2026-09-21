
import os
import subprocess
import sys
import time

def check_env(config):
    '''
    Check that correct environment is active.
    List of valid environments is given in config-publisher.yaml.
    '''
    if ('venv' in config) and ('conda env' in config):
        raise ValueError('config-publisher.yaml should specify either venv or conda env, not both')
    if 'venv' in config:
        valid_envs = config['venv']
        valid_envs_realpath = [os.path.realpath(env) for env in valid_envs]
        if 'VIRTUAL_ENV' not in os.environ:
            raise ValueError('No venv is activated')
        if os.environ['VIRTUAL_ENV'] not in valid_envs_realpath:
            msg = ['To run commands, activate one of the valid environments (set in config-publisher.yaml):']
            for env in valid_envs:
                msg.append(f'  {env}')
            msg.append('Example: ')
            cmd = 'source ' + os.path.join(env, 'bin/activate')
            msg.append(f'  {cmd}')
            raise OSError('\n'.join(msg))

    elif 'conda env' in config:
        valid_envs = config['conda env']
        if 'CONDA_DEFAULT_ENV' not in os.environ:
            raise ValueError('No conda env is activated')
        if os.environ['CONDA_DEFAULT_ENV'] not in valid_envs:
            msg = ['To run commands, activate one of the valid environments (set in config-publisher.yaml):']
            for env in valid_envs:
                msg.append(f'  {env}')
            msg.append('Example: ')
            cmd = f'conda activate {env}'
            msg.append(f'  {cmd}')
            raise OSError('\n'.join(msg))

    else:
        raise Exception('Need to specify env to run publishing commands')

def exec_cmds(commands: list[str], cmd_args: dict, do_cmds: bool = True, retries: int = 0) -> list[dict]:
    '''
    Execute list of commands.
    Checks return codes of commands and stops if a command fails.
    If do_cmds=False, the commands that would have been executed are displayed (without running them).

    Arguments
    ---------
    commands: list[str]
        List of command templates. Example of one command template:
        "esgmapfile make --project {project} --outdir {mapfile_path} --directory {dataset_path}"
    cmd_args: dict
        Argument:value pairs to substitute into command templates. Example:
        {'project': 'cmip7'}
    do_cmds: bool
        True ==> execute the commands
        False ==> show the commands that would be executed, but don't execute them
    retries: int
        Number of times to retry a command if it fails.
        retries = 0 ==> only try it once

    Returns
    -------
    exit_status: int
        Exit status of last command executed (0 = success).
    '''
    cmds = []
    for cmd in commands:
        cmds.append( cmd.format(**cmd_args) )

    exit_status = None
    attempt = 1
    max_attempts = 1 + retries
    start_time = time.time()
    cmd_results = []
    for cmd in cmds:
        cmd_result = {'cmd': cmd}
        cmd_results.append(cmd_result)
        if do_cmds:
            while attempt <= max_attempts:
                if attempt > 1:
                    # Show message saying this is a retry
                    print(f'Returned exit status={exit_status}, retrying (attempt {attempt} of {max_attempts})')
                print(cmd)

                # Using subprocess.run works fine but the stdout is not seen by the user
                # result = subprocess.run(cmd.split(), capture_output=True, text=True)
                # exit_status = result.returncode

                # Using subprocess.Popen allows user to see the stdout
                result = subprocess.Popen(
                    cmd.split(),
                    stdout=sys.stdout, # preserves colour (if any) in the stdout
                    stderr=sys.stderr,
                    text=True,
                )
                result.communicate()
                exit_status = result.returncode

                cmd_result.update({'exit_status': exit_status, 'attempt': attempt})
                if exit_status == 0:
                    # Command has succeeded, so exit the retry loop
                    break
                else:
                    # Command failed
                    attempt += 1

            if exit_status != 0:
                # If the command did not ultimately succeed (whether it was tried many times or just once),
                # don't attempt subsequent commands (if any).
                cmd_result['time_taken'] = time.time() - start_time
                break

        else:
            # Show command that would have been executed
            print(cmd)
            cmd_result.update({'exit_status': 'N/A', 'attempt': 0})

        # Record time taken to complete the command (units: seconds)
        cmd_result['time_taken'] = time.time() - start_time

    return cmd_results

def log_cmds(dataset_id: str, cmd_results: dict) -> str:
    '''
    Write success/fail status of commands.
    '''
    msg = []
    for cmd_result in cmd_results:
        msg += [cmd_result['cmd']]
        exit_status, attempt = cmd_result['exit_status'], cmd_result['attempt']
        time_taken = str('%.4f' % cmd_result['time_taken'])
        details = f'exit_status: {exit_status}, attempts: {attempt}, time: {time_taken} s'
        if cmd_result['exit_status'] == 0:
            msg += [f'SUCCESS - {details}']
        else:
            msg += [f'FAIL - {details}']
    msg = [f'   {s}' for s in msg]
    return msg
