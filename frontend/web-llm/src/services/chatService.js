import { post } from './api'

export async function sendMessage(message) {
  return post('/chat/send', { message })
}
