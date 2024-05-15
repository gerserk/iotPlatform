# iotPlatform
This is a project I made for an IOT platform which uses as main core DeviceHive https://devicehive.com/. I added a GUI (which is property of Aquaseek https://aquaseek.tech/ so won't be available), the architecture works with an NGINX instance that serves all the incoming requests to the 3 main blocks of the platform:

- a service catalog, that gives back endpoints of every other service
- an InfluxDB instance https://www.influxdata.com/ to store telemetry data
- the Devicehive block

to setup the platform use the docker-compose command with all its files
