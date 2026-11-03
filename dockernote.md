#for building and running
docker compose up -d --build

#for running
docker compose up -d

docker compose restart #run after you make a change

docker compose down # Stop and remove project containers

#see containers
docker ps
#see all
docker ps -a

#stop delete
docker rm -f mysecretnotes

#delete stopped containers
docker container prune -f
docker system prune -a #deletes everything not used

#how much space used
docker system df
