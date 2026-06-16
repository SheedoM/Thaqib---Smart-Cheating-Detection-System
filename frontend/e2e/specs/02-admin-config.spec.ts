import { expect, test } from '@playwright/test';
import { env, uniqueName } from '../fixtures/env';
import { expectOkJson, login, logout, mutate } from '../fixtures/api';

test.describe('admin configuration workflow', () => {
  test('creates hall, camera, microphone, user, exam, and assignment through public APIs', async () => {
    const admin = await login(env.adminUsername, env.adminPassword);
    const institutionId = String(admin.user.institution_id);
    const suffix = uniqueName('full-config');

    const hall = await expectOkJson(await mutate(admin, 'post', '/api/halls/', {
      data: {
        institution_id: institutionId,
        name: `Hall ${suffix}`,
        building: 'E2E Building',
        floor: '2',
        capacity: 42,
        status: 'ready',
      },
    }));

    const camera = await expectOkJson(await mutate(admin, 'post', '/api/devices/', {
      data: {
        hall_id: hall.id,
        type: 'camera',
        identifier: `cam-${suffix}`,
        stream_url: `${env.simulatorURL}/camera/hall101_cam_front/feed`,
        position: { label: 'Front Camera' },
        status: 'online',
      },
    }));

    const mic = await expectOkJson(await mutate(admin, 'post', '/api/devices/', {
      data: {
        hall_id: hall.id,
        type: 'microphone',
        identifier: `mic-${suffix}`,
        stream_url: `${env.simulatorURL}/mic/hall101_mic_front/feed`,
        position: { label: 'Front Mic' },
        status: 'online',
      },
    }));

    const placement = await mutate(admin, 'put', `/api/devices/${mic.id}/placements`, {
      data: {
        placements: [{ camera_id: String(camera.id), norm_pos: [0.5, 0.5] }],
      },
    });
    await expect(placement, await placement.text()).toBeOK();

    const invigilator = await expectOkJson(await mutate(admin, 'post', '/api/users/', {
      data: {
        institution_id: institutionId,
        username: `invig_${Date.now()}`,
        password: 'Invigilator123!',
        email: `${suffix}@example.test`,
        full_name: 'E2E Invigilator',
        role: 'invigilator',
      },
    }));

    const start = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    const end = new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString();
    const exam = await expectOkJson(await mutate(admin, 'post', '/api/sessions/', {
      data: {
        exam_name: `Exam ${suffix}`,
        exam_type: 'e2e',
        scheduled_start: start,
        scheduled_end: end,
        status: 'scheduled',
        student_count: 42,
        hall_ids: [hall.id],
      },
    }));

    const assignment = await mutate(admin, 'post', `/api/sessions/${exam.id}/assignments`, {
      data: {
        invigilator_id: invigilator.id,
        hall_id: hall.id,
        role: 'secondary',
      },
    });
    await expect(assignment, await assignment.text()).toBeOK();

    const report = await admin.api.get(`/api/sessions/${exam.id}/report`);
    await expect(report, await report.text()).toBeOK();
    expect(await report.json()).toMatchObject({
      session_id: exam.id,
      exam_name: exam.exam_name,
    });

    await logout(admin);
  });
});
