./cloud_sql_proxy -instances="cloud2-task2:asia-southeast1:todo-database"=tcp:2929&
export SQLALCHEMY_DATABASE_URI=postgresql://rhitik:test123@127.0.0.1:2929/test
export FLASK_APP=/home/lambainsaan/codes/assignments/paid_assignments/cloud_computing/app.py
export FLASK_ENV=development
export GOOGLE_APPLICATION_CREDENTIALS="/home/lambainsaan/Downloads/Cloud2-72912752e454.json"
./env/bin/python -m flask run >app.log 2>&1
