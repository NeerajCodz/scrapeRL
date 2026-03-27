# ⚙️ Dashboard Settings

## Table of Contents
1. [Overview](#overview)
2. [Memory Settings](#memory-settings)
3. [API & Model Settings](#api--model-settings)
4. [MCP Server Management](#mcp-server-management)
5. [Agent Behavior](#agent-behavior)
6. [Search Engine Configuration](#search-engine-configuration)
7. [Network & Proxy](#network--proxy)
8. [Cost Control](#cost-control)
9. [Performance Tuning](#performance-tuning)
10. [Import/Export](#importexport)

---

## Overview

The **Settings Dashboard** provides comprehensive configuration for all aspects of the WebScraper environment, models, MCPs, agents, and observability.

### Settings Structure

```
Settings
├── Memory
│   ├── Short-Term Memory
│   ├── Working Memory
│   ├── Long-Term Memory
│   └── Shared Memory
├── API & Models
│   ├── OpenAI
│   ├── Anthropic
│   ├── Google
│   ├── Groq
│   ├── Custom Providers
│   └── Model Routing
├── MCP Servers
│   ├── Installed Servers
│   ├── Available Servers
│   └── Custom Servers
├── Agent Behavior
│   ├── Exploration vs Exploitation
│   ├── Retry Strategy
│   ├── Planning Depth
│   └── Risk Tolerance
├── Search Engines
│   ├── Google Search
│   ├── Bing Search
│   ├── Brave Search
│   └── DuckDuckGo
├── Network & Proxy
│   ├── Proxy Pool
│   ├── VPN Configuration
│   ├── Rate Limiting
│   └── User Agent Rotation
├── Cost Control
│   ├── Daily Budget
│   ├── Model Costs
│   └── Alerts
└── Performance
    ├── Batch Processing
    ├── Parallel Execution
    ├── Caching
    └── Context Optimization
```

---

## Memory Settings

### Configuration

```typescript
interface MemorySettings {
  // Layer toggles
  enableShortTerm: boolean;          // Episode memory
  enableWorking: boolean;            // Reasoning buffer
  enableLongTerm: boolean;           // Persistent patterns
  enableShared: boolean;             // Multi-agent memory
  
  // Size limits
  maxEpisodeMemoryMB: number;        // Default: 10
  maxWorkingMemoryItems: number;     // Default: 50
  maxLongTermPatterns: number;       // Default: 10000
  
  // Vector database
  vectorDB: {
    provider: 'faiss' | 'qdrant' | 'pinecone' | 'weaviate';
    embeddingModel: string;          // Default: 'text-embedding-3-small'
    dimension: number;               // Default: 1536
    similarityMetric: 'cosine' | 'euclidean' | 'dot_product';
  };
  
  // Storage backend
  storage: {
    backend: 'filesystem' | 'postgresql' | 'mongodb' | 'redis';
    path: string;                    // For filesystem
    connectionString?: string;        // For databases
  };
  
  // Optimization
  autoPrune: boolean;                // Default: true
  pruneThreshold: number;            // Default: 0.3 (keep if score > 0.3)
  pruneIntervalHours: number;        // Default: 24
  autoSummarize: boolean;            // Default: true
  maxContextTokens: number;          // Default: 4000
}
```

### UI Component

```jsx
<MemorySettings>
  <Section title="Memory Layers">
    <Toggle label="Short-Term Memory (Episode)" value={enableShortTerm} />
    <Toggle label="Working Memory (Reasoning)" value={enableWorking} />
    <Toggle label="Long-Term Memory (Persistent)" value={enableLongTerm} />
    <Toggle label="Shared Memory (Multi-Agent)" value={enableShared} />
  </Section>
  
  <Section title="Size Limits">
    <NumberInput label="Episode Memory (MB)" value={maxEpisodeMemoryMB} min={1} max={100} />
    <NumberInput label="Working Memory Items" value={maxWorkingMemoryItems} min={10} max={500} />
    <NumberInput label="Long-Term Patterns" value={maxLongTermPatterns} min={100} max={100000} />
  </Section>
  
  <Section title="Vector Database">
    <Select label="Provider" options={['FAISS', 'Qdrant', 'Pinecone', 'Weaviate']} />
    <Select label="Embedding Model" options={['text-embedding-3-small', 'text-embedding-3-large', 'custom']} />
    <NumberInput label="Dimension" value={dimension} disabled />
    <Select label="Similarity Metric" options={['Cosine', 'Euclidean', 'Dot Product']} />
  </Section>
  
  <Section title="Auto-Optimization">
    <Toggle label="Auto-Prune Low-Value Memories" value={autoPrune} />
    <Slider label="Prune Threshold" value={pruneThreshold} min={0} max={1} step={0.1} />
    <NumberInput label="Prune Interval (hours)" value={pruneIntervalHours} />
    <Toggle label="Auto-Summarize Episodes" value={autoSummarize} />
    <NumberInput label="Max Context Tokens" value={maxContextTokens} />
  </Section>
</MemorySettings>
```

---

## API & Model Settings

### Multi-Provider Configuration

```typescript
interface APISettings {
  providers: {
    openai?: {
      apiKey: string;
      organization?: string;
      models: {
        default: string;
        reasoning: string;
        fast: string;
      };
      temperature: number;
      maxTokens: number;
    };
    
    anthropic?: {
      apiKey: string;
      models: {
        default: string;
        reasoning: string;
        fast: string;
      };
      temperature: number;
      maxTokens: number;
    };
    
    google?: {
      apiKey: string;
      models: {
        default: string;
        reasoning: string;
        fast: string;
      };
      temperature: number;
      maxOutputTokens: number;
    };
    
    groq?: {
      apiKey: string;
      models: {
        default: string;
        reasoning: string;
        fast: string;
      };
      temperature: number;
      maxTokens: number;
    };
    
    custom?: {
      baseURL: string;
      apiKey: string;
      models: Record<string, string>;
    };
  };
  
  // Smart routing
  router: {
    enabled: boolean;
    strategy: 'task_based' | 'cost_optimized' | 'speed_optimized' | 'quality_optimized';
    fallbackOrder: string[];
    autoRetry: boolean;
    maxRetries: number;
  };
  
  // Ensemble
  ensemble: {
    enabled: boolean;
    strategy: 'voting' | 'ranking' | 'fusion' | 'verification';
    models: string[];
    minAgreement: number;
  };
}
```

### UI Component

```jsx
<APISettings>
  <Tabs>
    <Tab label="OpenAI">
      <TextInput label="API Key" type="password" value={openaiKey} />
      <TextInput label="Organization (optional)" value={openaiOrg} />
      <Select label="Default Model" options={['gpt-4o-mini', 'gpt-4-turbo', 'gpt-4o']} />
      <Select label="Reasoning Model" options={['gpt-4-turbo', 'gpt-4o']} />
      <Select label="Fast Model" options={['gpt-4o-mini', 'gpt-3.5-turbo']} />
      <Button onClick={testConnection}>Test Connection</Button>
    </Tab>
    
    <Tab label="Anthropic">
      <TextInput label="API Key" type="password" value={anthropicKey} />
      <Select label="Default Model" options={['claude-3-5-sonnet', 'claude-3-opus']} />
      <Button onClick={testConnection}>Test Connection</Button>
    </Tab>
    
    <Tab label="Google">
      <TextInput label="API Key" type="password" value={googleKey} />
      <Select label="Default Model" options={['gemini-1.5-flash', 'gemini-1.5-pro']} />
      <Button onClick={testConnection}>Test Connection</Button>
    </Tab>
    
    <Tab label="Groq">
      <TextInput label="API Key" type="password" value={groqKey} />
      <Select label="Default Model" options={['llama-3.1-70b-versatile', 'llama-3.1-405b']} />
      <Button onClick={testConnection}>Test Connection</Button>
    </Tab>
    
    <Tab label="Custom">
      <TextInput label="Base URL" value={customBaseURL} placeholder="http://localhost:11434/v1" />
      <TextInput label="API Key" type="password" value={customKey} />
      <DynamicList label="Models" items={customModels} />
      <Button onClick={testConnection}>Test Connection</Button>
    </Tab>
  </Tabs>
  
  <Section title="Smart Model Routing">
    <Toggle label="Enable Smart Routing" value={routerEnabled} />
    <Select label="Strategy" options={['Task-Based', 'Cost Optimized', 'Speed Optimized', 'Quality Optimized']} />
    <SortableList label="Fallback Order" items={fallbackOrder} />
    <Toggle label="Auto-Retry on Failure" value={autoRetry} />
    <NumberInput label="Max Retries" value={maxRetries} min={1} max={10} />
  </Section>
  
  <Section title="Model Ensemble">
    <Toggle label="Enable Ensemble (⚠️ Increases Cost)" value={ensembleEnabled} />
    <Select label="Strategy" options={['Voting', 'Ranking', 'Fusion', 'Verification']} />
    <MultiSelect label="Models" options={allModels} selected={ensembleModels} />
    <Slider label="Min Agreement (%)" value={minAgreement} min={50} max={100} />
  </Section>
</APISettings>
```

---

## MCP Server Management

### Configuration

```typescript
interface MCPSettings {
  servers: Record<string, MCPServerConfig>;
  
  autoDiscoverTools: boolean;
  toolTimeout: number;              // Seconds
  maxConcurrentCalls: number;
  retryFailedCalls: boolean;
  cacheToolResults: boolean;
  cacheTTL: number;                 // Seconds
}

interface MCPServerConfig {
  command: string;
  args: string[];
  enabled: boolean;
  autoDownload: boolean;
  config: Record<string, any>;
  
  // Metadata
  name: string;
  description: string;
  category: string;
  installSize: string;
  status: 'installed' | 'not_installed' | 'downloading' | 'error';
}
```

### UI Component

```jsx
<MCPServerManagement>
  <Tabs>
    <Tab label="Installed">
      <ServerList>
        {installedServers.map(server => (
          <ServerCard key={server.name}>
            <ServerIcon category={server.category} />
            <ServerInfo>
              <Title>{server.name}</Title>
              <Description>{server.description}</Description>
              <Meta>
                <Badge>{ server.category}</Badge>
                <Badge>{server.toolCount} tools</Badge>
              </Meta>
            </ServerInfo>
            <Actions>
              <Toggle value={server.enabled} onChange={toggleServer} />
              <Button onClick={() => testServer(server)}>Test</Button>
              <Button onClick={() => uninstallServer(server)}>Uninstall</Button>
            </Actions>
          </ServerCard>
        ))}
      </ServerList>
    </Tab>
    
    <Tab label="Available">
      <SearchInput placeholder="Search MCP servers..." />
      <FilterBar>
        <Filter label="All" />
        <Filter label="Parsing" />
        <Filter label="Browser" />
        <Filter label="Database" />
        <Filter label="Search" />
      </FilterBar>
      
      <ServerGallery>
        {availableServers.map(server => (
          <ServerCard key={server.name}>
            <ServerIcon category={server.category} />
            <Title>{server.name}</Title>
            <Description>{server.description}</Description>
            <InstallSize>{server.installSize}</InstallSize>
            <Button onClick={() => installServer(server)}>
              Install
            </Button>
          </ServerCard>
        ))}
      </ServerGallery>
    </Tab>
    
    <Tab label="Custom">
      <Form onSubmit={addCustomServer}>
        <TextInput label="Server Name" required />
        <TextInput label="Command" placeholder="python" required />
        <TextInput label="Arguments" placeholder="-m mcp_server" required />
        <JsonEditor label="Config (JSON)" />
        <Button type="submit">Add Server</Button>
      </Form>
    </Tab>
  </Tabs>
  
  <Section title="Global MCP Settings">
    <Toggle label="Auto-Discover Tools on Startup" value={autoDiscoverTools} />
    <NumberInput label="Tool Timeout (seconds)" value={toolTimeout} />
    <NumberInput label="Max Concurrent Calls" value={maxConcurrentCalls} />
    <Toggle label="Retry Failed Calls" value={retryFailedCalls} />
    <Toggle label="Cache Tool Results" value={cacheToolResults} />
    <NumberInput label="Cache TTL (seconds)" value={cacheTTL} />
  </Section>
</MCPServerManagement>
```

---

## Agent Behavior

### Configuration

```typescript
interface AgentBehaviorSettings {
  // Exploration vs Exploitation
  explorationRate: number;           // 0.0 = exploit only, 1.0 = explore only
  explorationDecay: number;          // Decay rate per episode
  
  // Planning
  planningDepth: number;             // How many steps ahead to plan
  replanThreshold: number;           // Replan if reward drops by X%
  
  // Retry strategy
  maxRetries: number;                // Per action
  retryDelay: number;                // Seconds
  adaptiveRetry: boolean;            // Increase delay after each failure
  
  // Risk tolerance
  riskTolerance: 'conservative' | 'balanced' | 'aggressive';
  
  // Memory usage
  memoryIntensity: 'low' | 'medium' | 'high';
  
  // Learning
  learningRate: number;
  enableOnlineLearning: boolean;
  updateMemoryAfterEpisode: boolean;
}
```

### UI Component

```jsx
<AgentBehaviorSettings>
  <Section title="Exploration Strategy">
    <Slider label="Exploration Rate" value={explorationRate} min={0} max={1} step={0.1} />
    <HelpText>
      0.0 = Always use best known strategy (exploit)
      1.0 = Always try new approaches (explore)
    </HelpText>
    <Slider label="Exploration Decay" value={explorationDecay} min={0} max={0.1} step={0.01} />
  </Section>
  
  <Section title="Planning">
    <Slider label="Planning Depth" value={planningDepth} min={1} max={10} />
    <HelpText>How many steps ahead the agent plans (higher = slower but smarter)</HelpText>
    <NumberInput label="Replan Threshold (%)" value={replanThreshold} min={0} max={100} />
  </Section>
  
  <Section title="Retry Strategy">
    <NumberInput label="Max Retries" value={maxRetries} min={0} max={10} />
    <NumberInput label="Retry Delay (seconds)" value={retryDelay} min={0} max={60} />
    <Toggle label="Adaptive Retry (exponential backoff)" value={adaptiveRetry} />
  </Section>
  
  <Section title="Risk Tolerance">
    <RadioGroup value={riskTolerance}>
      <Radio value="conservative">
        <Label>Conservative</Label>
        <Description>Prefer proven patterns, avoid risky actions</Description>
      </Radio>
      <Radio value="balanced">
        <Label>Balanced</Label>
        <Description>Balance exploration and exploitation</Description>
      </Radio>
      <Radio value="aggressive">
        <Label>Aggressive</Label>
        <Description>Try new approaches quickly, higher failure tolerance</Description>
      </Radio>
    </RadioGroup>
  </Section>
  
  <Section title="Memory & Learning">
    <Select label="Memory Intensity" options={['Low', 'Medium', 'High']} />
    <Toggle label="Enable Online Learning" value={enableOnlineLearning} />
    <Toggle label="Update Memory After Each Episode" value={updateMemoryAfterEpisode} />
  </Section>
</AgentBehaviorSettings>
```

---

## Search Engine Configuration

### Configuration

```typescript
interface SearchEngineSettings {
  default: 'google' | 'bing' | 'brave' | 'duckduckgo' | 'perplexity';
  
  google?: {
    apiKey: string;
    searchEngineId: string;
    region: string;
    safeSearch: boolean;
  };
  
  bing?: {
    apiKey: string;
    market: string;
  };
  
  brave?: {
    apiKey: string;
    country: string;
  };
  
  duckduckgo?: {
    region: string;
    safeSearch: boolean;
  };
  
  perplexity?: {
    apiKey: string;
    model: string;
  };
  
  // Global settings
  maxResults: number;
  timeout: number;
  cacheResults: boolean;
  cacheTTL: number;
}
```

### UI Component

```jsx
<SearchEngineSettings>
  <Select label="Default Search Engine" options={['Google', 'Bing', 'Brave', 'DuckDuckGo', 'Perplexity']} />
  
  <Tabs>
    <Tab label="Google">
      <TextInput label="API Key" type="password" />
      <TextInput label="Search Engine ID" />
      <Select label="Region" options={regions} />
      <Toggle label="Safe Search" />
      <Button onClick={testGoogle}>Test</Button>
    </Tab>
    
    <Tab label="Bing">
      <TextInput label="API Key" type="password" />
      <Select label="Market" options={markets} />
      <Button onClick={testBing}>Test</Button>
    </Tab>
    
    <Tab label="Brave">
      <TextInput label="API Key" type="password" />
      <Select label="Country" options={countries} />
      <Button onClick={testBrave}>Test</Button>
    </Tab>
    
    <Tab label="DuckDuckGo">
      <Info>No API key required (free)</Info>
      <Select label="Region" options={regions} />
      <Toggle label="Safe Search" />
    </Tab>
    
    <Tab label="Perplexity">
      <TextInput label="API Key" type="password" />
      <Select label="Model" options={['pplx-70b-online', 'pplx-7b-online']} />
      <Button onClick={testPerplexity}>Test</Button>
    </Tab>
  </Tabs>
  
  <Section title="Global Settings">
    <NumberInput label="Max Results" value={maxResults} min={1} max={100} />
    <NumberInput label="Timeout (seconds)" value={timeout} min={5} max={60} />
    <Toggle label="Cache Results" value={cacheResults} />
    <NumberInput label="Cache TTL (seconds)" value={cacheTTL} />
  </Section>
</SearchEngineSettings>
```

---

## Network & Proxy

### Configuration

```typescript
interface NetworkSettings {
  proxy: {
    enabled: boolean;
    pools: ProxyPool[];
    rotationStrategy: 'round_robin' | 'random' | 'health_based';
    maxRetries: number;
  };
  
  vpn: {
    enabled: boolean;
    provider: string;
    server: string;
    credentials: {
      username: string;
      password: string;
    };
  };
  
  rateLimiting: {
    enabled: boolean;
    requestsPerSecond: number;
    burstSize: number;
  };
  
  userAgent: {
    rotationEnabled: boolean;
    customUserAgents: string[];
  };
  
  timeout: {
    connect: number;
    read: number;
  };
}
```

### UI - See [proxy-vpn.md](./WebScraper_OpenEnv_SoftwareDoc.md#9-network-layer--vpn--proxy) for full details

---

## Cost Control

### Configuration

```typescript
interface CostControlSettings {
  dailyBudget: number;               // USD
  monthlyBudget: number;             // USD
  alertThresholds: number[];         // [0.5, 0.8, 0.9] = 50%, 80%, 90%
  
  modelCosts: Record<string, { input: number; output: number }>;
  
  enforcements: {
    stopOnBudgetExceeded: boolean;
    downgradeToCheaperModel: boolean;
    notifyOnHighCost: boolean;
  };
}
```

### UI Component

```jsx
<CostControlSettings>
  <Section title="Budgets">
    <NumberInput label="Daily Budget (USD)" value={dailyBudget} prefix="$" />
    <NumberInput label="Monthly Budget (USD)" value={monthlyBudget} prefix="$" />
    
    <CurrentUsage>
      <Stat>
        <Label>Today</Label>
        <Value>${todayCost.toFixed(2)} / ${dailyBudget.toFixed(2)}</Value>
        <ProgressBar value={todayCost / dailyBudget} />
      </Stat>
      <Stat>
        <Label>This Month</Label>
        <Value>${monthCost.toFixed(2)} / ${monthlyBudget.toFixed(2)}</Value>
        <ProgressBar value={monthCost / monthlyBudget} />
      </Stat>
    </CurrentUsage>
  </Section>
  
  <Section title="Alerts">
    <TagInput label="Alert Thresholds (%)" values={alertThresholds} />
    <HelpText>Get notified at these percentages of budget</HelpText>
  </Section>
  
  <Section title="Enforcement">
    <Toggle label="Stop Execution on Budget Exceeded" value={stopOnBudgetExceeded} />
    <Toggle label="Auto-Downgrade to Cheaper Model" value={downgradeToCheaperModel} />
    <Toggle label="Notify on High-Cost Requests" value={notifyOnHighCost} />
  </Section>
  
  <Section title="Model Costs">
    <Table>
      <thead>
        <tr>
          <th>Model</th>
          <th>Input (per 1M tokens)</th>
          <th>Output (per 1M tokens)</th>
          <th>Estimated Cost/Episode</th>
        </tr>
      </thead>
      <tbody>
        {models.map(model => (
          <tr key={model.name}>
            <td>{model.name}</td>
            <td>${model.inputCost.toFixed(2)}</td>
            <td>${model.outputCost.toFixed(2)}</td>
            <td>${model.estimatedCostPerEpisode.toFixed(4)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  </Section>
</CostControlSettings>
```

---

## Performance Tuning

### Configuration

```typescript
interface PerformanceSettings {
  batchProcessing: {
    enabled: boolean;
    batchSize: number;
    maxConcurrent: number;
  };
  
  parallelExecution: {
    enabled: boolean;
    maxWorkers: number;
  };
  
  caching: {
    enabled: boolean;
    cacheHTML: boolean;
    cacheAPIResponses: boolean;
    cacheDuration: number;            // Seconds
    maxCacheSize: number;             // MB
  };
  
  contextOptimization: {
    enabled: boolean;
    summarizeOldObservations: boolean;
    pruneThreshold: number;
    maxContextTokens: number;
  };
}
```

---

## Import/Export

```jsx
<ImportExportSettings>
  <Section title="Export Settings">
    <Button onClick={exportAll}>Export All Settings (JSON)</Button>
    <Button onClick={exportMemory}>Export Memory Database</Button>
    <Button onClick={exportLogs}>Export Logs</Button>
  </Section>
  
  <Section title="Import Settings">
    <FileUpload label="Import Settings (JSON)" accept=".json" onChange={importSettings} />
    <Button onClick={resetToDefaults}>Reset to Defaults</Button>
  </Section>
</ImportExportSettings>
```

---

**Next:** See [rewards.md](./rewards.md) for advanced reward function design.
