# FASE 1: build de React
FROM node:20 AS build
WORKDIR /app
# Copia solo los manifiestos primero para cachear dependencias
COPY package*.json ./
RUN npm ci || npm install
# Ahora el resto del código
COPY . .
RUN npm run build


FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
