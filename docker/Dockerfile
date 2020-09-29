FROM thinkwhere/gdal-python:3.6-shippable

# Update base container install
RUN apt-get update

# Custom dir
WORKDIR /data

# This will install GDAL 2.4.2
RUN pip install --upgrade pip
RUN pip3 -V
RUN pip check
RUN pip list
RUN curl 'http://naver.com'
###
RUN pip install opencv-python==4.4.0.42
RUN pip install numba==0.51.1
RUN pip install numpy==1.19.1


#CMD ["python", "/home/innopam/sandbox/application"]

EXPOSE 9190
