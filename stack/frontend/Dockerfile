# Etapa 1: build
FROM node:20 AS build
WORKDIR /app
# Copia solo manifiestos primero para cachear dependencias
COPY package.json package-lock.json* ./
RUN npm ci || npm install
# Copia el resto del código
COPY . .
RUN npm run build

# Etapa 2: servidor estático
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

