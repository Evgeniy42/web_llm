import { post, get } from './api'

export async function register({ username, email, password }) {
  return post('/user/register', { username, email, password })
}

export async function login({ email, password }) {
  return post('/user/login', { email, password })
}

export async function getUserById(userId) {
  return get(`/user/${userId}`)
}
