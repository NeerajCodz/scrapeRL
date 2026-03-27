# 🎯 Advanced Reward Function

## Table of Contents
1. [Overview](#overview)
2. [Reward Components](#reward-components)
3. [Planning Quality](#planning-quality)
4. [Recovery Ability](#recovery-ability)
5. [Exploration Bonus](#exploration-bonus)
6. [Redundancy Penalty](#redundancy-penalty)
7. [Generalization Score](#generalization-score)
8. [Tool Usage Efficiency](#tool-usage-efficiency)
9. [Memory Utilization](#memory-utilization)
10. [Final Reward Formula](#final-reward-formula)
11. [Configuration](#configuration)

---

## Overview

The **Advanced Reward Function** provides dense, interpretable signals that guide the agent toward intelligent, efficient, and generalizable web scraping strategies.

### Design Principles

1. **Dense Rewards:** Provide feedback at every step, not just terminal states
2. **Interpretable:** Each component has a clear purpose agents (and humans) can understand
3. **Balanced:** Prevent reward hacking by balancing conflicting objectives
4. **Adaptive:** Adjust weights based on task difficulty and agent progress

### Basic vs Advanced

**Basic Reward (existing):**
```python
reward = task_completion_score  # 0.0 to 1.0
```

**Advanced Reward:**
```python
reward = (
    w1 * task_completion +
    w2 * efficiency +
    w3 * planning_quality +
    w4 * recovery_ability +
    w5 * exploration_bonus +
    w6 * tool_usage +
    w7 * memory_usage +
    w8 * generalization
) - penalties
```

---

## Reward Components

### 1. Task Completion (w1 = 0.40)

**Purpose:** Measure how much of the task is complete.

**Calculation:**
```python
def task_completion_score(extracted: Dict, ground_truth: Dict) -> float:
    """Score based on field completeness and accuracy."""
    if not ground_truth:
        return 0.0
    
    total_fields = len(ground_truth)
    correct_fields = 0
    partial_fields = 0
    
    for field, true_value in ground_truth.items():
        extracted_value = extracted.get(field)
        
        if extracted_value is None:
            continue  # Missing field, 0 points
        
        # Exact match
        if normalize(extracted_value) == normalize(true_value):
            correct_fields += 1
        # Partial match (fuzzy)
        elif similarity(extracted_value, true_value) > 0.7:
            partial_fields += 1
    
    score = (correct_fields + 0.5 * partial_fields) / total_fields
    return score
```

**Example:**
```python
# Task: Extract name, price, rating
ground_truth = {"name": "Widget Pro", "price": "$49.99", "rating": "4.5"}

# Agent extracted 2/3 correctly
extracted = {"name": "Widget Pro", "price": "$49.99", "rating": None}
task_completion = 2/3 = 0.67
```

---

### 2. Efficiency (w2 = 0.15)

**Purpose:** Reward completing tasks quickly with fewer actions.

**Calculation:**
```python
def efficiency_score(steps_taken: int, max_steps: int, pages_visited: int) -> float:
    """Lower steps and pages = higher efficiency."""
    # Step efficiency
    step_efficiency = 1.0 - (steps_taken / max_steps)
    
    # Page efficiency (prefer fewer page visits)
    ideal_pages = estimate_ideal_page_count(task)
    page_efficiency = 1.0 - abs(pages_visited - ideal_pages) / ideal_pages
    page_efficiency = max(0.0, page_efficiency)
    
    return 0.7 * step_efficiency + 0.3 * page_efficiency
```

**Example:**
```python
# Task with max 20 steps
steps_taken = 8
efficiency = 1.0 - (8/20) = 0.60  # Good!

steps_taken = 18
efficiency = 1.0 - (18/20) = 0.10  # Inefficient
```

---

## Planning Quality

### 3. Planning Quality Score (w3 = 0.10)

**Purpose:** Reward agents that plan before acting.

**Signals:**
- Used WRITE_MEMORY with reasoning notes
- Actions follow a coherent strategy
- Fewer backtracking actions

**Calculation:**
```python
def planning_quality_score(episode_history: List[Action]) -> float:
    """Measure planning behavior."""
    score = 0.0
    
    # 1. Did agent write reasoning notes?
    reasoning_actions = [a for a in episode_history if a.notes]
    if reasoning_actions:
        score += 0.3
    
    # 2. Action coherence: Do actions follow a logical sequence?
    coherence = measure_action_coherence(episode_history)
    score += 0.4 * coherence
    
    # 3. Backtracking penalty: Visiting same page multiple times
    unique_pages = len(set(a.navigate_to for a in episode_history if a.navigate_to))
    total_navigations = len([a for a in episode_history if a.action_type == "NAVIGATE"])
    if total_navigations > 0:
        backtrack_ratio = 1.0 - (unique_pages / total_navigations)
        score += 0.3 * (1.0 - backtrack_ratio)  # Lower backtracking = higher score
    
    return min(score, 1.0)

def measure_action_coherence(actions: List[Action]) -> float:
    """Are actions logically connected?"""
    coherence_patterns = [
        # Good patterns
        ("SEARCH_PAGE", "EXTRACT_FIELD"),      # Search then extract
        ("NAVIGATE", "EXTRACT_FIELD"),          # Navigate then extract
        ("EXTRACT_FIELD", "VERIFY_FACT"),       # Extract then verify
        ("SEARCH_ENGINE", "NAVIGATE"),          # Search then visit
    ]
    
    coherent_pairs = 0
    total_pairs = len(actions) - 1
    
    for i in range(total_pairs):
        pair = (actions[i].action_type, actions[i+1].action_type)
        if pair in coherence_patterns:
            coherent_pairs += 1
    
    return coherent_pairs / total_pairs if total_pairs > 0 else 0.0
```

**Example:**
```python
# Good planning:
actions = [
    Action(type="SEARCH_PAGE", notes="Looking for price pattern"),
    Action(type="EXTRACT_FIELD", target="price"),
    Action(type="VERIFY_FACT", field="price")
]
planning_score = 0.3 (notes) + 0.4*0.67 (coherence) + 0.3 (no backtrack) = 0.87

# Poor planning:
actions = [
    Action(type="NAVIGATE", navigate_to="/page1"),
    Action(type="NAVIGATE", navigate_to="/page2"),
    Action(type="NAVIGATE", navigate_to="/page1"),  # Backtrack!
    Action(type="EXTRACT_FIELD")
]
planning_score = 0.0 (no notes) + 0.4*0.0 (incoherent) + 0.3*0.33 (backtracking) = 0.10
```

---

## Recovery Ability

### 4. Recovery Ability Score (w4 = 0.08)

**Purpose:** Reward agents that recover from failures.

**Signals:**
- Action failed → Agent tried alternative approach
- Extraction returned empty → Agent searched with different selector
- Page blocked → Agent switched proxy/VPN

**Calculation:**
```python
def recovery_ability_score(episode_history: List[Tuple[Action, Reward]]) -> float:
    """Measure ability to recover from failures."""
    recoveries = 0
    failures = 0
    
    for i in range(len(episode_history) - 1):
        action, reward = episode_history[i]
        next_action, next_reward = episode_history[i + 1]
        
        # Detect failure (negative reward or empty result)
        if reward.value < 0 or "failed" in reward.message.lower():
            failures += 1
            
            # Check if next action was a recovery attempt
            if is_recovery_action(action, next_action):
                if next_reward.value > reward.value:  # Recovery succeeded
                    recoveries += 1
    
    return recoveries / failures if failures > 0 else 0.0

def is_recovery_action(failed_action: Action, next_action: Action) -> bool:
    """Is next_action a recovery attempt for failed_action?"""
    # Same action type with different parameters
    if failed_action.action_type == next_action.action_type:
        if failed_action.selector != next_action.selector:
            return True  # Tried different selector
    
    # Switched to alternative action type
    recovery_alternatives = {
        "EXTRACT_FIELD": ["SEARCH_PAGE", "INSPECT_ELEMENT"],
        "NAVIGATE": ["FETCH_URL"],  # Try direct fetch if navigate blocked
        "SEARCH_ENGINE": ["NAVIGATE"],  # Try direct URL if search fails
    }
    
    if next_action.action_type in recovery_alternatives.get(failed_action.action_type, []):
        return True
    
    return False
```

**Example:**
```python
# Good recovery:
history = [
    (Action(type="EXTRACT_FIELD", selector=".price"), Reward(value=-0.1, message="Not found")),
    (Action(type="SEARCH_PAGE", query="price"), Reward(value=0.2, message="Found price pattern")),
    (Action(type="EXTRACT_FIELD", selector="span.product-price"), Reward(value=0.5, message="Extracted"))
]
recovery_score = 1/1 = 1.0  # 1 failure, 1 successful recovery

# No recovery:
history = [
    (Action(type="EXTRACT_FIELD", selector=".price"), Reward(value=-0.1)),
    (Action(type="EXTRACT_FIELD", selector=".price"), Reward(value=-0.1)),  # Repeated same failed action!
    (Action(type="SUBMIT"), Reward(value=0.0))
]
recovery_score = 0/2 = 0.0  # 2 failures, 0 recoveries
```

---

## Exploration Bonus

### 5. Exploration Bonus (w5 = 0.05)

**Purpose:** Encourage discovering new pages and patterns early in training.

**Calculation:**
```python
def exploration_bonus(
    pages_visited: List[str],
    known_pages: Set[str],  # From long-term memory
    episode_number: int
) -> float:
    """Bonus for discovering new pages/patterns."""
    new_pages = set(pages_visited) - known_pages
    
    # Bonus decreases over time (we want agent to eventually exploit)
    decay_factor = math.exp(-0.01 * episode_number)
    
    # Bonus per new page discovered
    bonus_per_page = 0.1
    
    return min(len(new_pages) * bonus_per_page * decay_factor, 1.0)
```

**Example:**
```python
# Episode 10: Agent discovers 3 new pages
exploration_bonus = 3 * 0.1 * exp(-0.01*10) = 0.3 * 0.90 = 0.27

# Episode 500: Same discovery
exploration_bonus = 3 * 0.1 * exp(-0.01*500) = 0.3 * 0.007 = 0.002  # Minimal bonus now
```

---

## Redundancy Penalty

### 6. Redundancy Penalty (penalty, not bonus)

**Purpose:** Penalize visiting the same page repeatedly without progress.

**Calculation:**
```python
def redundancy_penalty(pages_visited: List[str]) -> float:
    """Penalty for revisiting pages."""
    from collections import Counter
    visit_counts = Counter(pages_visited)
    
    penalty = 0.0
    for page, count in visit_counts.items():
        if count > 1:
            # Exponential penalty for repeat visits
            penalty += 0.05 * (count - 1) ** 1.5
    
    return min(penalty, 1.0)
```

**Example:**
```python
pages = ["/page1", "/page2", "/page1", "/page1", "/page3"]
# page1 visited 3 times
redundancy_penalty = 0.05 * (3-1)**1.5 = 0.05 * 2.83 = 0.14
```

---

## Generalization Score

### 7. Generalization Score (w8 = 0.07)

**Purpose:** Reward strategies that work across different page layouts.

**Measurement:** After training, evaluate agent on unseen task variations.

**Calculation:**
```python
def generalization_score(
    agent: Agent,
    test_tasks: List[Task],
    training_tasks: List[Task]
) -> float:
    """Test agent on unseen variations of trained tasks."""
    test_results = []
    
    for task in test_tasks:
        # Ensure task is not in training set
        if task.id in [t.id for t in training_tasks]:
            continue
        
        result = agent.run(task)
        test_results.append(result.completion_score)
    
    # Average performance on unseen tasks
    return np.mean(test_results) if test_results else 0.0
```

---

## Tool Usage Efficiency

### 8. Tool Usage (w6 = 0.05)

**Purpose:** Reward using the right tools at the right time.

**Calculation:**
```python
def tool_usage_score(actions: List[Action]) -> float:
    """Reward appropriate tool usage."""
    score = 0.0
    
    # 1. Used memory appropriately
    memory_actions = [a for a in actions if a.action_type in ["READ_MEMORY", "WRITE_MEMORY"]]
    if memory_actions:
        score += 0.3
    
    # 2. Used MCP tools when appropriate
    mcp_actions = [a for a in actions if a.action_type == "MCP_TOOL_CALL"]
    if mcp_actions:
        score += 0.3
    
    # 3. Verified important extractions
    verify_actions = [a for a in actions if a.action_type == "VERIFY_FACT"]
    extract_actions = [a for a in actions if a.action_type == "EXTRACT_FIELD"]
    if verify_actions and extract_actions:
        verification_ratio = len(verify_actions) / len(extract_actions)
        score += 0.4 * min(verification_ratio, 1.0)
    
    return min(score, 1.0)
```

---

## Memory Utilization

### 9. Memory Usage (w7 = 0.05)

**Purpose:** Reward effective use of memory system.

**Calculation:**
```python
def memory_usage_score(episode: Episode) -> float:
    """Reward effective memory usage."""
    score = 0.0
    
    # 1. Did agent query long-term memory for similar patterns?
    if episode.memory_queries > 0:
        score += 0.4
    
    # 2. Did agent write successful patterns to long-term memory?
    if episode.memory_writes > 0:
        score += 0.3
    
    # 3. Did memory queries lead to successful actions?
    memory_assisted_success = episode.memory_assisted_actions / episode.total_actions
    score += 0.3 * memory_assisted_success
    
    return min(score, 1.0)
```

---

## Final Reward Formula

### Complete Formula

```python
def calculate_reward(episode: Episode, config: RewardConfig) -> Reward:
    """Calculate comprehensive reward."""
    
    # Positive components
    R_completion = task_completion_score(episode.extracted, episode.ground_truth)
    R_efficiency = efficiency_score(episode.steps, episode.max_steps, len(episode.pages))
    R_planning = planning_quality_score(episode.actions)
    R_recovery = recovery_ability_score(episode.history)
    R_exploration = exploration_bonus(episode.pages, episode.memory.known_pages, episode.number)
    R_tools = tool_usage_score(episode.actions)
    R_memory = memory_usage_score(episode)
    R_generalization = generalization_score(episode.agent, episode.test_tasks, episode.training_tasks)
    
    # Penalties
    P_redundancy = redundancy_penalty(episode.pages)
    P_timeout = 1.0 if episode.timed_out else 0.0
    P_invalid = sum(1 for a in episode.actions if not a.valid) * 0.1
    
    # Weighted sum
    w = config.weights
    reward_value = (
        w.completion * R_completion +
        w.efficiency * R_efficiency +
        w.planning * R_planning +
        w.recovery * R_recovery +
        w.exploration * R_exploration +
        w.tools * R_tools +
        w.memory * R_memory +
        w.generalization * R_generalization
    ) - (P_redundancy + P_timeout + P_invalid)
    
    # Clamp to [-1, 1]
    reward_value = max(-1.0, min(1.0, reward_value))
    
    # Build breakdown for interpretability
    breakdown = {
        "task_completion": R_completion,
        "efficiency": R_efficiency,
        "planning_quality": R_planning,
        "recovery_ability": R_recovery,
        "exploration_bonus": R_exploration,
        "tool_usage": R_tools,
        "memory_usage": R_memory,
        "generalization": R_generalization,
        "redundancy_penalty": -P_redundancy,
        "timeout_penalty": -P_timeout,
        "invalid_action_penalty": -P_invalid
    }
    
    # Generate explanation
    message = generate_reward_explanation(breakdown, reward_value)
    
    return Reward(
        value=reward_value,
        cumulative=episode.cumulative_reward + reward_value,
        breakdown=breakdown,
        message=message
    )
```

### Default Weights

```python
class RewardWeights(BaseModel):
    completion: float = 0.40      # Most important
    efficiency: float = 0.15       # Moderate importance
    planning: float = 0.10         # Encourages good habits
    recovery: float = 0.08         # Resilience
    exploration: float = 0.05      # Early training
    tools: float = 0.05            # Appropriate tool use
    memory: float = 0.05           # Effective memory
    generalization: float = 0.07   # Transfer learning
    # Total: 0.95, leaves room for penalties
```

---

## Configuration

### Settings

```typescript
interface RewardConfig {
  weights: RewardWeights;
  
  // Component toggles
  enablePlanningReward: boolean;
  enableRecoveryReward: boolean;
  enableExplorationBonus: boolean;
  enableGeneralizationTest: boolean;
  
  // Penalty settings
  redundancyThreshold: number;       // Penalize after N visits to same page
  timeoutPenalty: number;            // Penalty for exceeding time limit
  invalidActionPenalty: number;      // Penalty per invalid action
  
  // Exploration decay
  explorationDecayRate: number;      // Default: 0.01
  
  // Generalization
  testTaskCount: number;             // Number of unseen tasks to test on
}
```

### UI Component

```jsx
<RewardSettings>
  <Section title="Component Weights">
    <Slider label="Task Completion" value={weights.completion} min={0} max={1} step={0.05} />
    <Slider label="Efficiency" value={weights.efficiency} min={0} max={1} step={0.05} />
    <Slider label="Planning Quality" value={weights.planning} min={0} max={1} step={0.05} />
    <Slider label="Recovery Ability" value={weights.recovery} min={0} max={1} step={0.05} />
    <Slider label="Exploration Bonus" value={weights.exploration} min={0} max={1} step={0.05} />
    <Slider label="Tool Usage" value={weights.tools} min={0} max={1} step={0.05} />
    <Slider label="Memory Usage" value={weights.memory} min={0} max={1} step={0.05} />
    <Slider label="Generalization" value={weights.generalization} min={0} max={1} step={0.05} />
    
    <TotalWeight value={Object.values(weights).reduce((a,b) => a+b, 0)} max={1.0} />
  </Section>
  
  <Section title="Penalties">
    <NumberInput label="Redundancy Threshold (page visits)" value={redundancyThreshold} />
    <NumberInput label="Timeout Penalty" value={timeoutPenalty} min={0} max={1} step={0.1} />
    <NumberInput label="Invalid Action Penalty" value={invalidActionPenalty} min={0} max={1} step={0.1} />
  </Section>
  
  <Section title="Exploration">
    <NumberInput label="Decay Rate" value={explorationDecayRate} min={0} max={0.1} step={0.001} />
    <HelpText>How quickly exploration bonus decreases over episodes</HelpText>
  </Section>
  
  <Section title="Presets">
    <Button onClick={() => loadPreset('balanced')}>Balanced (Default)</Button>
    <Button onClick={() => loadPreset('efficiency_focused')}>Efficiency Focused</Button>
    <Button onClick={() => loadPreset('quality_focused')}>Quality Focused</Button>
    <Button onClick={() => loadPreset('exploration')}>Exploration Mode</Button>
  </Section>
</RewardSettings>
```

---

## Reward Visualization

```jsx
<RewardBreakdown>
  <BarChart>
    {Object.entries(breakdown).map(([component, value]) => (
      <Bar 
        key={component}
        label={component}
        value={value}
        color={value >= 0 ? 'green' : 'red'}
      />
    ))}
  </BarChart>
  
  <TotalReward value={reward.value} />
  
  <Explanation>{reward.message}</Explanation>
</RewardBreakdown>
```

**Example Output:**
```
Reward Breakdown (Total: 0.72)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task Completion:    ████████████████████ 0.85
Efficiency:         ████████████░░░░░░░░ 0.65
Planning Quality:   ███████████████░░░░░ 0.78
Recovery Ability:   ██████████████████░░ 0.90
Exploration:        ████░░░░░░░░░░░░░░░░ 0.20
Tool Usage:         ███████████████████░ 0.95
Memory Usage:       ████████░░░░░░░░░░░░ 0.40
Generalization:     ██████████████░░░░░░ 0.72
Redundancy Penalty: ░░░░░░░░░░░░░░░░░░░░ -0.15
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Explanation:
✓ Excellent task completion (85% of fields extracted correctly)
✓ Good efficiency (completed in 8/20 steps)
✓ Strong recovery ability (recovered from 2/2 failures)
⚠ Moderate redundancy (visited homepage 3 times)
→ Overall: Strong performance!
```

---

**Next:** See [html-processing.md](./html-processing.md) for advanced HTML handling.
