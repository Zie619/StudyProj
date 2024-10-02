postgres:	
	docker run --name postgres17 -p 5432:5432 -e POSTGRES_USER=root -e POSTGRES_PASSWORD=eliadad -d postgres:17-alpine
createdb:	
	docker exec -it postgres17 createdb --username=root --owner=root studyo_proj

dropdb:	
	docker exec -it postgres17 dropdb studyo_proj

updatesql:
	alembic revision --autogenerate # after changing the matadata files (users.py etc..)

migrateup:
	alembic upgrade head

migratedown:
	alembic downgrade -1  # can use alembic history to find revision list and downgrade specific (e.g., a12bcde34f67)  example alembic downgrade a12bcde34f67

.PHONY:	createdb dropdb	postgres migrateup migratedown 