import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';

class AppController extends ChangeNotifier {
  AppController({ApiClient? api, FlutterSecureStorage? storage})
    : api = api ?? ApiClient(),
      _storage = storage ?? const FlutterSecureStorage();
  final ApiClient api;
  final FlutterSecureStorage _storage;
  static const _tokenKey = 'qingqing_session_token';
  bool authenticated = false;
  bool busy = false;
  bool advancedMode = false;
  bool memoryEnabled = true;
  String credentialPreference = 'platform_first';
  String preferredTone = '';
  String styleNotes = '';
  String avoidNotes = '';
  String? devCode;
  String? error;

  List<dynamic> activeRuns = [];
  List<dynamic> artifacts = [];
  List<dynamic> memoryItems = [];
  Map<String, dynamic>? entitlements;
  final Set<String> _pollingRunIds = {};

  Future<void> restoreSession() async {
    if (kIsWeb) return;
    final token = await _storage.read(key: _tokenKey);
    if (token == null || token.isEmpty) return;
    api.token = token;
    try {
      await api.request('/api/v1/me/entitlements');
      authenticated = true;
      await Future.wait([
        loadEntitlements(),
        loadPreferences(),
        loadRuns(),
        loadArtifacts(),
        loadMemory(),
      ]);
    } on ApiException {
      await _storage.delete(key: _tokenKey);
      api.token = null;
    }
  }

  Future<void> requestCode(String email) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/auth/email/request-code',
        method: 'POST',
        body: {'email': email},
      );
      devCode = data['dev_code']?.toString();
    });
  }

  Future<void> verifyCode(String email, String code) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/auth/email/verify',
        method: 'POST',
        body: {'email': email, 'code': code},
      );
      api.token = data['access_token']?.toString();
      authenticated = api.token != null;
      final token = api.token;
      if (!kIsWeb && token != null) {
        await _storage.write(key: _tokenKey, value: token);
      }
      await Future.wait([
        loadEntitlements(),
        loadPreferences(),
        loadRuns(),
        loadArtifacts(),
        loadMemory(),
      ]);
    });
  }

  Future<void> loadEntitlements() async {
    try {
      final data = await api.request('/api/v1/me/entitlements');
      entitlements = data;
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadPreferences() async {
    try {
      final data = await api.request('/api/v1/me/preferences');
      advancedMode = data['advanced_mode_enabled'] == true;
      credentialPreference =
          data['credential_preference']?.toString() ?? 'platform_first';
      memoryEnabled = data['memory_enabled'] != false;
      preferredTone = data['preferred_tone']?.toString() ?? '';
      styleNotes = data['style_notes']?.toString() ?? '';
      avoidNotes = data['avoid_notes']?.toString() ?? '';
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadMemory({String? query}) async {
    try {
      final path = query == null || query.isEmpty
          ? '/api/v1/memory?limit=30'
          : '/api/v1/memory?limit=30&q=${Uri.encodeQueryComponent(query)}';
      final data = await api.request(path);
      memoryItems = List<dynamic>.from(data['items'] as List<dynamic>? ?? []);
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    } catch (_) {
      // Offline / settings shell without backend should not crash UI.
      notifyListeners();
    }
  }

  Future<void> loadArtifacts() async {
    try {
      final data = await api.request('/api/v1/artifacts');
      artifacts = data['artifacts'] as List<dynamic>? ?? [];
      notifyListeners();
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<void> loadRuns() async {
    try {
      final data = await api.request('/api/v1/agent/runs');
      activeRuns = List<dynamic>.from(
        data['runs'] as List<dynamic>? ?? const [],
      );
      notifyListeners();
      for (final run in activeRuns) {
        if (run['status'] == 'running') {
          unawaited(_pollRun(run['id'].toString()));
        }
      }
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
      error = exception.message;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> submitAgentRun(
    String goal,
    Map<String, dynamic> routing, {
    String? skillId,
    bool autoPlan = true,
  }) async {
    return await _guard(() async {
      final data = await api.request(
        '/api/v1/agent/runs',
        method: 'POST',
        headers: {
          'Idempotency-Key': DateTime.now().microsecondsSinceEpoch.toString(),
        },
        body: {
          'goal': goal,
          'routing': routing,
          'skill_id': ?skillId,
          'auto_plan': autoPlan,
        },
      );
      var current = data;
      if (data['status'] == 'planned') {
        current = await api.request(
          '/api/v1/agent/runs/${data['id']}/execute',
          method: 'POST',
        );
      }
      final newRun = Map<String, dynamic>.from(current);
      activeRuns = [
        newRun,
        ...activeRuns.where((item) => item['id'] != newRun['id']),
      ];
      if (newRun['status'] == 'running') {
        unawaited(_pollRun(newRun['id'].toString()));
      }
      await loadEntitlements();
      await loadArtifacts();
      return newRun;
    });
  }

  Future<void> executeRun(String runId) async {
    await _guard(() async {
      await api.request('/api/v1/agent/runs/$runId/execute', method: 'POST');
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx)
              {...activeRuns[i], 'status': 'running'}
            else
              activeRuns[i],
        ];
      }
      unawaited(_pollRun(runId));
      await loadArtifacts();
    });
  }

  Future<void> approveRun(String runId) async {
    await _guard(() async {
      await api.request('/api/v1/agent/runs/$runId/approve', method: 'POST');
      final data = await api.request(
        '/api/v1/agent/runs/$runId/execute',
        method: 'POST',
      );
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx) data else activeRuns[i],
        ];
      }
      unawaited(_pollRun(runId));
      await loadEntitlements();
    });
  }

  Future<void> cancelRun(String runId) async {
    await _guard(() async {
      final data = await api.request(
        '/api/v1/agent/runs/$runId/cancel',
        method: 'POST',
      );
      final idx = activeRuns.indexWhere((r) => r['id'] == runId);
      if (idx != -1) {
        activeRuns = [
          for (var i = 0; i < activeRuns.length; i++)
            if (i == idx) data else activeRuns[i],
        ];
      }
      await loadEntitlements();
    });
  }

  Future<void> savePreferences({
    bool? advanced,
    String? credential,
    bool? memory,
    String? tone,
    String? style,
    String? avoid,
  }) async {
    await _guard(() async {
      final body = <String, Object>{};
      if (advanced != null) {
        body['advanced_mode_enabled'] = advanced;
      }
      if (credential != null) {
        body['credential_preference'] = credential;
      }
      if (memory != null) {
        body['memory_enabled'] = memory;
      }
      if (tone != null) {
        body['preferred_tone'] = tone;
      }
      if (style != null) {
        body['style_notes'] = style;
      }
      if (avoid != null) {
        body['avoid_notes'] = avoid;
      }
      final data = await api.request(
        '/api/v1/me/preferences',
        method: 'PATCH',
        body: body,
      );
      advancedMode = data['advanced_mode_enabled'] == true;
      credentialPreference =
          data['credential_preference']?.toString() ?? credentialPreference;
      memoryEnabled = data['memory_enabled'] != false;
      preferredTone = data['preferred_tone']?.toString() ?? preferredTone;
      styleNotes = data['style_notes']?.toString() ?? styleNotes;
      avoidNotes = data['avoid_notes']?.toString() ?? avoidNotes;
      await loadEntitlements();
    });
  }

  Future<void> addMemoryNote(String content) async {
    await _guard(() async {
      await api.request(
        '/api/v1/memory',
        method: 'POST',
        body: {'content': content, 'kind': 'note'},
      );
      await loadMemory();
    });
  }

  Future<void> deleteMemoryItem(String id) async {
    await _guard(() async {
      await api.request('/api/v1/memory/$id', method: 'DELETE');
      memoryItems = memoryItems.where((item) => item['id'] != id).toList();
    });
  }

  Future<void> logout() async {
    if (!kIsWeb) await _storage.delete(key: _tokenKey);
    api.token = null;
    authenticated = false;
    advancedMode = false;
    memoryEnabled = true;
    preferredTone = '';
    styleNotes = '';
    avoidNotes = '';
    credentialPreference = 'platform_first';
    activeRuns = [];
    artifacts = [];
    memoryItems = [];
    entitlements = null;
    _pollingRunIds.clear();
    notifyListeners();
  }

  Future<void> _pollRun(String runId) async {
    // Allow local-loopback runs without a session token; stop only when a
    // second poller is already active for the same id.
    if (!_pollingRunIds.add(runId)) {
      return;
    }
    try {
      for (var attempt = 0; attempt < 30; attempt++) {
        await Future<void>.delayed(
          Duration(
            milliseconds: attempt < 2 ? 500 : (attempt < 8 ? 1500 : 4000),
          ),
        );
        final data = await api.request('/api/v1/agent/runs/$runId');
        final updated = Map<String, dynamic>.from(data);
        activeRuns = [
          updated,
          ...activeRuns.where((item) => item['id'] != runId),
        ];
        notifyListeners();
        final status = updated['status']?.toString();
        if ({'completed', 'failed', 'cancelled', 'paused'}.contains(status)) {
          await Future.wait([loadArtifacts(), loadEntitlements()]);
          return;
        }
      }
    } on ApiException catch (exception) {
      if (exception.statusCode == 401) await logout();
    } finally {
      _pollingRunIds.remove(runId);
    }
  }

  Future<T?> _guard<T>(Future<T> Function() action) async {
    busy = true;
    error = null;
    notifyListeners();
    try {
      return await action();
    } on ApiException catch (exception) {
      error = exception.message;
      return null;
    } catch (exception) {
      // Browser CORS / network failures throw ClientException, not ApiException.
      // Without this, "获取验证码" appears to do nothing.
      final text = exception.toString();
      if (text.contains('Failed to fetch') ||
          text.contains('ClientException') ||
          text.contains('XMLHttpRequest') ||
          text.contains('NetworkError')) {
        error = '无法连接后端 API（请确认 8001 已启动，且 CORS 允许当前页面来源）';
      } else {
        error = '请求失败：$text';
      }
      return null;
    } finally {
      busy = false;
      notifyListeners();
    }
  }
}
