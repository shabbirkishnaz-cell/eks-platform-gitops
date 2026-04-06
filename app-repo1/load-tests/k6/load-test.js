import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 20 },   // ramp to 20 users
    { duration: '3m', target: 50 },   // ramp to 50 users
    { duration: '5m', target: 100 },  // ramp to 100 users
    { duration: '5m', target: 100 },  // hold
    { duration: '2m', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://k8s-todoprod-3ff45627d7-1072646075.us-east-1.elb.amazonaws.com/';
const PASSWORD = __ENV.PASSWORD || 'Password123!';
const TOTAL_USERS = Number(__ENV.TOTAL_USERS || 50);

function getUsername() {
  const userId = ((__VU - 1) % TOTAL_USERS) + 1;
  return `user${userId}`;
}

export default function () {
  const username = getUsername();

  const commonHeaders = {
    'Content-Type': 'application/json',
  };

  // 1. login
  const loginPayload = JSON.stringify({
    username: username,
    password: PASSWORD,
  });

  const loginRes = http.post(`${BASE_URL}/api/login`, loginPayload, {
    headers: commonHeaders,
    tags: { endpoint: 'login' },
  });

  check(loginRes, {
    'login status is 200': (r) => r.status === 200,
  });

  // 2. get todos
  const listRes1 = http.get(
    `${BASE_URL}/api/todos?username=${encodeURIComponent(username)}`,
    {
      headers: commonHeaders,
      tags: { endpoint: 'list_todos_before' },
    }
  );

  check(listRes1, {
    'initial list status is 200': (r) => r.status === 200,
  });

  // 3. create todo
  const createPayload = JSON.stringify({
    username: username,
    title: `k6 todo from ${username} vu${__VU} iter${__ITER}`,
  });

  const createRes = http.post(`${BASE_URL}/api/todos`, createPayload, {
    headers: commonHeaders,
    tags: { endpoint: 'create_todo' },
  });

  check(createRes, {
    'create todo status is 200': (r) => r.status === 200 || r.status === 201,
  });

  let createdTodoId = null;
  try {
    const body = JSON.parse(createRes.body);
    if (body && body.todo && body.todo.id) {
      createdTodoId = body.todo.id;
    }
  } catch (e) {
    // ignore parse failure
  }

  // 4. get todos again
  const listRes2 = http.get(
    `${BASE_URL}/api/todos?username=${encodeURIComponent(username)}`,
    {
      headers: commonHeaders,
      tags: { endpoint: 'list_todos_after' },
    }
  );

  check(listRes2, {
    'second list status is 200': (r) => r.status === 200,
  });

  // 5. delete created todo if id returned
  if (createdTodoId !== null) {
    const deleteRes = http.del(
      `${BASE_URL}/api/todos/${createdTodoId}?username=${encodeURIComponent(username)}`,
      null,
      {
        headers: commonHeaders,
        tags: { endpoint: 'delete_todo' },
      }
    );

    check(deleteRes, {
      'delete todo status is 200': (r) => r.status === 200 || r.status === 204,
    });
  }

  sleep(1);
}