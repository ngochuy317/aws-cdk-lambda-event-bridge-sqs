## Application code
To be able to successfully import common and local service folders within IDEA please add apps as Source in IDEA Interpreter settings. 


## Code quality and unit tests
### Install
    pip install pylint
    pip install coverage

### Run linter (code quality) from apps folder
    pylint {module}
Example
> pylint common/sms

### Run unit test coverage from apps folder
    coverage run --source={module} -m pytest -v {module} && coverage report -m
Example
>  coverage run --source=sms/sms_check -m pytest -v sms/sms_check && coverage report -m
