import 'package:flutter/material.dart';
import '../app_controller.dart';

class AgentPage extends StatefulWidget {
  const AgentPage({
    super.key,
    required this.controller,
    this.capability = 'chat',
  });
  final AppController controller;
  final String capability;
  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends State<AgentPage> {
  final goal = TextEditingController();
  final budget = TextEditingController(text: '10');
  List<dynamic> models = [];
  String model = 'auto';
  Map<String, dynamic>? run;
  bool loading = false;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
    _loadModels();
  }

  void _onControllerChanged() {
    final runId = run?['id']?.toString();
    if (runId == null || !mounted) return;
    final updated = widget.controller.activeRuns
        .where((item) => item['id'] == runId)
        .firstOrNull;
    if (updated == null) return;
    setState(() => run = Map<String, dynamic>.from(updated));
  }

  Future<void> _loadModels() async {
    try {
      final data = await widget.controller.api.request(
        '/api/v1/models?capability=${widget.capability}',
      );
      if (mounted) {
        setState(() => models = data['models'] as List<dynamic>? ?? []);
      }
    } catch (_) {}
  }

  Future<void> _create() async {
    if (goal.text.trim().isEmpty) return;
    setState(() => loading = true);
    final routing = {
      'capability': widget.capability,
      'mode': model == 'auto' ? 'auto' : 'preferred',
      'preferred_model_id': model == 'auto' ? null : model,
      'credential_preference': widget.controller.credentialPreference,
      'stage_overrides': <String, String>{},
      'budget_limit': double.tryParse(budget.text),
    };
    final data = await widget.controller.submitAgentRun(
      goal.text.trim(),
      routing,
    );
    if (!mounted) return;
    setState(() {
      run = data == null ? null : Map<String, dynamic>.from(data);
      loading = false;
    });
    if (data == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('任务创建失败，请重试')));
    }
  }

  Future<void> _approve() async {
    final runId = run?['id']?.toString();
    if (runId == null) return;
    setState(() => loading = true);
    await widget.controller.approveRun(runId);
    if (!mounted) return;
    setState(() => loading = false);
    _syncRun(runId);
  }

  Future<void> _cancel() async {
    final runId = run?['id']?.toString();
    if (runId == null) return;
    setState(() => loading = true);
    await widget.controller.cancelRun(runId);
    if (!mounted) return;
    setState(() => loading = false);
    _syncRun(runId);
  }

  void _syncRun(String runId) {
    if (!mounted) return;
    final updated = widget.controller.activeRuns
        .where((item) => item['id'] == runId)
        .firstOrNull;
    if (updated != null) {
      setState(() => run = Map<String, dynamic>.from(updated));
    }
  }

  String? _extractOutput(Map<String, dynamic> value) {
    final invocations = value['invocations'] as List<dynamic>? ?? const [];
    for (final raw in invocations) {
      if (raw is! Map) continue;
      final output = raw['output'];
      if (output is Map && output['content'] != null) {
        return output['content'].toString();
      }
      if (output is Map && output['url'] != null) {
        return '产物链接：${output['url']}';
      }
      if (output is Map && output['artifact_id'] != null) {
        return '作品 ID：${output['artifact_id']}';
      }
    }
    return null;
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    goal.dispose();
    budget.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(24),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          widget.capability == 'image' ? '轻青图片创作' : '轻青创作 Agent',
          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
        ),
        const Text('描述目标，Auto 会平衡质量、成本与速度。完成后会展示真实模型输出。'),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: model,
                decoration: const InputDecoration(
                  labelText: '模型',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: 'auto',
                    child: Text('Auto · 推荐'),
                  ),
                  ...models
                      .where((item) => item['availability'] == 'available')
                      .map(
                        (item) => DropdownMenuItem<String>(
                          value: item['id'].toString(),
                          child: Text(item['display_name'].toString()),
                        ),
                      ),
                ],
                onChanged: (value) => setState(() => model = value ?? 'auto'),
              ),
            ),
            const SizedBox(width: 12),
            SizedBox(
              width: 120,
              child: TextField(
                controller: budget,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: '任务预算',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: TextField(
            controller: goal,
            expands: true,
            maxLines: null,
            minLines: null,
            textAlignVertical: TextAlignVertical.top,
            decoration: InputDecoration(
              hintText: widget.capability == 'image'
                  ? '例如：生成一张清新自然的产品主视觉…'
                  : '例如：根据产品照片制作一段 15 秒介绍视频…',
              border: const OutlineInputBorder(),
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (run case final value?) _buildRunCard(value),
        FilledButton.icon(
          onPressed: loading ? null : _create,
          icon: const Icon(Icons.auto_awesome),
          label: Text(loading ? '处理中…' : '开始创作'),
        ),
      ],
    ),
  );

  Widget _buildRunCard(Map<String, dynamic> value) {
    final invocations = value['invocations'] as List<dynamic>? ?? const [];
    final invocation = invocations.isEmpty
        ? null
        : invocations.first as Map<String, dynamic>;
    final selectedModel = invocation?['model'] as Map<String, dynamic>?;
    final status = value['status']?.toString() ?? 'unknown';
    final output = _extractOutput(value);
    final statusLine = switch (status) {
      'awaiting_approval' =>
        '预计消耗 ${value['estimated_cost']} 额度，需要确认后执行。',
      'running' || 'planned' => '任务 ${value['id']} 执行中…',
      'completed' => '任务 ${value['id']} 已完成。',
      'failed' => '任务失败：${value['error_code'] ?? '未知错误'}',
      'paused' => '任务已暂停：${value['pause_reason'] ?? value['error_code'] ?? ''}',
      'cancelled' => '任务已取消。',
      _ => '任务 ${value['id']} 已进入 $status 状态。',
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(statusLine),
            if (selectedModel != null) ...[
              const SizedBox(height: 8),
              Text(
                '实际安排：${selectedModel['provider']} · ${selectedModel['display_name']}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              Text(invocation?['routing_reason']?.toString() ?? 'Auto 路由'),
            ],
            if (output != null && output.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('输出', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              SelectableText(output),
            ],
            if (status == 'awaiting_approval') ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(onPressed: loading ? null : _cancel, child: const Text('取消任务')),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: loading ? null : _approve,
                    child: const Text('批准并执行'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
