FROM node:24

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

CMD ["npx", "tsx", "src/index.ts"]
