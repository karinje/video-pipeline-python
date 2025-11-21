# PRD: AI Video Generation Platform - Frontend & Backend Implementation

**Version:** 1.0  
**Date:** November 21, 2025  
**Target:** Node.js + Next.js on Vercel  
**Status:** Ready for Implementation

---

## 1. Executive Summary

Convert the existing Python video generation pipeline into a full-stack Node.js/Next.js application deployable on Vercel. The application will guide users through creating eyewear/sunglasses video advertisements by:

1. Selecting a pre-built template with universe objects (characters, locations, props)
2. Uploading brand logo and providing brand details
3. Reviewing and editing scene descriptions across multiple tabs
4. Generating first frame images using Replicate (nano-banana-pro)
5. Generating video clips using Replicate (Veo 3 Fast / Sora 2)
6. Merging clips into final video

All intermediate outputs will be stored in Vercel Blob Storage or Postgres.

---

## 2. Reference Architecture

### 2.1 Existing Frontend (Reference)
- **Location:** `/Users/sanjaykarinje/git/video-gen/bluesam1-video-pipeline/frontend/`
- **Tech Stack:** Next.js 16, React 19, TypeScript, shadcn/ui, Tailwind CSS
- **Key Components:**
  - `app/page.tsx` - Main orchestration
  - `components/home-screen.tsx` - Project selection
  - `components/template-selection-step.tsx` - Template gallery
  - `components/scenes-step.tsx` - Scene configuration
  - `components/video-editor-step.tsx` - Preview/editing
  - `components/video-step.tsx` - Final export

### 2.2 Existing Backend Reference
- **Location:** `/Users/sanjaykarinje/git/video-gen/bluesam1-video-pipeline/script/`
- **Key Files:**
  - `ai/concepts.js` - OpenAI concept generation
  - `ai/images.js` - Replicate image generation
  - `ai/frames.js` - First frame generation
  - `ai/veo.js` - Video generation
  - `pipeline.js` - Orchestration

### 2.3 Python Pipeline Reference
Critical steps to replicate:

| Step | Python Path | Key Outputs | Node.js Equivalent |
|------|-------------|-------------|-------------------|
| S1 | `s1_generate_concepts/` | Concept variations | Skip (using templates) |
| S4 | `s4_revise_concept/` | Scene descriptions | Template JSON |
| S5 | `s5_generate_universe/` | Universe objects | Pre-loaded templates |
| S6 | `s6_generate_reference_images/` | Character/prop/location images | Template assets |
| S7 | `s7_generate_scene_prompts/` | Detailed video/audio prompts | Backend API |
| S8 | `s8_generate_first_frames/` | First frame images | Backend API → Replicate |
| S9 | `s9_generate_video_clips/` | Video clips | Backend API → Replicate |
| S10 | `s10_merge_clips/` | Final video | Backend API → FFmpeg |

---

## 3. Data Models

### 3.1 Template Structure

**Reference:** `/Users/sanjaykarinje/git/video-gen/s5_generate_universe/outputs/sunvue_1121_0921/sunvue_focus_finds_you_revised/sunvue_focus_finds_you_revised_universe_characters.json`

```typescript
interface UniverseCharacters {
  universe: {
    locations: UniverseLocation[];
    props: UniverseProp[];
  };
  characters: UniverseCharacter[];
}

interface UniverseLocation {
  name: string; // e.g., "Urban City Streets"
  scenes_used: number[]; // [1, 3]
  canonical_state: string; // Long description
  image_generation_prompt: string;
  image_path?: string; // Added: path to generated image
}

interface UniverseProp {
  name: string; // e.g., "SunVue Aviator Classic Sunglasses"
  scenes_used: number[];
  canonical_state: string;
  image_generation_prompt: string;
  image_path?: string;
}

interface UniverseCharacter {
  name: string; // e.g., "Main Character - Urban Professional"
  scenes_used: number[];
  canonical_state: string;
  image_generation_prompt: string;
  image_path?: string;
}
```

**Template Discovery:**
- Scan `/Users/sanjaykarinje/git/video-gen/s5_generate_universe/outputs/` for all batch folders
- For each batch folder, find `*_universe_characters.json` files
- Load corresponding images from `/Users/sanjaykarinje/git/video-gen/s6_generate_reference_images/outputs/{batch_folder}/{concept_name}/`

**Image Path Pattern:**
```
s6_generate_reference_images/outputs/{batch_folder}/{concept_name}/
  characters/{character_name}/{character_name}_canonical.png
  locations/{location_name}/{location_name}_canonical.png
  props/{prop_name}/{prop_name}_canonical.png
```

**Example:**
```
s6_generate_reference_images/outputs/sunvue_1121_0921/sunvue_focus_finds_you_revised/
  characters/main_character_urban_professional/main_character_urban_professional_canonical.png
  locations/urban_city_streets/urban_city_streets_canonical.png
  props/sunvue_aviator_classic_sunglasses/sunvue_aviator_classic_sunglasses_canonical.png
```

### 3.2 Scene Structure

**Reference:** `/Users/sanjaykarinje/git/video-gen/s4_revise_concept/outputs/sunvue_1120_2106/sunvue_transformation_instant_upgrade_generic_gpt_5.1/sunvue_transformation_instant_upgrade_generic_gpt_5.1_revised.txt`

```typescript
interface RevisedScript {
  scenes: SceneDescription[]; // Parsed from text file
}

interface SceneDescription {
  scene_number: number; // 1-based
  title: string; // e.g., "SCENE 1"
  description: string; // Full scene text
}
```

**Parsing Logic:**
Parse text file where scenes start with `**SCENE {N}**:` pattern.

### 3.3 Detailed Scene Prompts

**Reference:** `/Users/sanjaykarinje/git/video-gen/s7_generate_scene_prompts/outputs/sunvue_1120_2106/sunvue_transformation_instant_upgrade_generic_gpt_5.1/sunvue_transformation_instant_upgrade_generic_gpt_5.1_scene_prompts.json`

```typescript
interface ScenePrompts {
  scenes: ScenePrompt[];
}

interface ScenePrompt {
  scene_number: number;
  duration_seconds: number; // 4, 6, or 8 (Veo 3 Fast) or 4, 8, 12 (Sora-2)
  video_prompt: string; // Detailed video generation prompt
  audio_background: string; // Music/sound description
  audio_dialogue: string | null; // Spoken dialogue
  first_frame_image_prompt: string; // Image generation prompt
  elements_used: {
    characters?: string[];
    locations?: string[];
    props?: string[];
  };
}
```

### 3.4 Brand Configuration

**Reference:** `/Users/sanjaykarinje/git/video-gen/s1_generate_concepts/inputs/configs/sunglasses.json`

```typescript
interface BrandConfig {
  // Required (user provides via UI)
  BRAND_NAME: string; // e.g., "SunVue"
  brand_logo?: string; // Blob storage URL after upload
  
  // Optional (collapsible section in UI)
  PRODUCT_DESCRIPTION?: string;
  BRAND_VALUES?: string;
  VALUE_PROPOSITION?: string;
  BRAND_PERSONALITY?: string;
  TAGLINE?: string;
  UNIQUE_SELLING_POINT?: string;
  TARGET_AUDIENCE?: string;
  
  // Product details (optional)
  FRAME_STYLE?: string;
  LENS_TYPE?: string;
  LENS_FEATURES?: string;
  STYLE_PERSONA?: string;
  WEARING_OCCASION?: string;
  FRAME_MATERIAL?: string;
  
  // Creative (optional)
  AD_STYLE?: string;
  CREATIVE_DIRECTION?: string;
}
```

### 3.5 Project Structure (Database Schema)

```typescript
interface Project {
  id: string; // UUID
  name: string; // User-provided project name
  template_id: string; // Which template was selected
  brand_config: BrandConfig;
  universe_data: UniverseCharacters; // Cached from template
  scene_prompts: ScenePrompts; // Generated or loaded from template
  first_frames: FirstFrameResult[]; // Generated images
  video_clips: VideoClipResult[]; // Generated videos
  final_video?: string; // Merged video URL
  created_at: Date;
  updated_at: Date;
  status: 'draft' | 'generating_frames' | 'generating_clips' | 'merging' | 'complete';
}

interface FirstFrameResult {
  scene_number: number;
  image_url: string; // Blob storage URL
  prompt_used: string;
  created_at: Date;
}

interface VideoClipResult {
  scene_number: number;
  video_url: string; // Blob storage URL or Replicate URL
  duration_seconds: number;
  prompt_used: string;
  created_at: Date;
}
```

---

## 4. Detailed Requirements

### 4.1 Step 1: Template Selection & Brand Input

#### 4.1.1 Template Loading

**Implementation:**

1. **Server-side template discovery** (Next.js API route: `/api/templates/list`)
   - Scan filesystem for universe JSON files
   - Load all templates from `/s5_generate_universe/outputs/`
   - Load corresponding images from `/s6_generate_reference_images/outputs/`
   - Cache in memory or Redis

**API Endpoint:**
```typescript
// app/api/templates/list/route.ts
export async function GET() {
  const templatesDir = path.join(process.cwd(), '../s5_generate_universe/outputs');
  const templates = [];
  
  // Scan all batch folders
  const batchFolders = fs.readdirSync(templatesDir);
  
  for (const batchFolder of batchFolders) {
    const batchPath = path.join(templatesDir, batchFolder);
    const conceptFolders = fs.readdirSync(batchPath);
    
    for (const conceptFolder of conceptFolders) {
      const universeFile = path.join(
        batchPath, 
        conceptFolder, 
        `${conceptFolder}_universe_characters.json`
      );
      
      if (fs.existsSync(universeFile)) {
        const universeData = JSON.parse(fs.readFileSync(universeFile, 'utf-8'));
        
        // Load images
        const imagesDir = path.join(
          process.cwd(), 
          '../s6_generate_reference_images/outputs',
          batchFolder,
          conceptFolder
        );
        
        // Attach image paths to universe objects
        universeData.characters = universeData.characters.map(char => ({
          ...char,
          image_url: `/api/templates/image?path=${encodeURIComponent(
            path.join(imagesDir, 'characters', sanitizeName(char.name), sanitizeName(char.name) + '_canonical.png')
          )}`
        }));
        
        // Similar for locations and props...
        
        templates.push({
          id: `${batchFolder}_${conceptFolder}`,
          name: conceptFolder.replace(/_/g, ' '),
          batch: batchFolder,
          universe: universeData,
          scene_script_path: path.join(
            process.cwd(),
            '../s4_revise_concept/outputs',
            batchFolder,
            conceptFolder,
            `${conceptFolder}_revised.txt`
          ),
          scene_prompts_path: path.join(
            process.cwd(),
            '../s7_generate_scene_prompts/outputs',
            batchFolder,
            conceptFolder,
            `${conceptFolder}_scene_prompts.json`
          )
        });
      }
    }
  }
  
  return Response.json({ templates });
}
```

**Helper Function:**
```typescript
function sanitizeName(name: string): string {
  // Convert "Main Character - Urban Professional" to "main_character_urban_professional"
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}
```

#### 4.1.2 UI Component Updates

**File:** `components/template-selection-step.tsx`

**Changes:**
- Modify to fetch templates from `/api/templates/list` instead of hardcoded array
- Display template thumbnails using first character/location image
- Show template metadata (name, number of scenes, elements count)

**File:** `components/scenes-step.tsx`

**Changes:**
1. **Brand Input Section** (top of page, before Elements):

```tsx
<section className="mb-8">
  <h2 className="mb-6 text-2xl font-semibold text-foreground">Brand Configuration</h2>
  
  {/* Brand Name - Always Visible */}
  <div className="mb-4">
    <label className="text-sm font-medium text-foreground">Brand Name *</label>
    <Input
      value={brandConfig.BRAND_NAME}
      onChange={(e) => updateBrandConfig('BRAND_NAME', e.target.value)}
      placeholder="e.g., SunVue"
      className="mt-1.5 max-w-md"
      required
    />
  </div>
  
  {/* Brand Logo Upload - Always Visible */}
  <div className="mb-4">
    <label className="text-sm font-medium text-foreground">Brand Logo *</label>
    <div className="mt-1.5">
      {brandConfig.brand_logo ? (
        <div className="relative w-32 h-32 border rounded">
          <Image src={brandConfig.brand_logo} fill className="object-contain p-2" alt="Brand logo" />
          <Button
            size="sm"
            variant="ghost"
            className="absolute top-1 right-1"
            onClick={() => updateBrandConfig('brand_logo', null)}
          >
            <X className="size-4" />
          </Button>
        </div>
      ) : (
        <div
          onClick={() => logoInputRef.current?.click()}
          className="w-32 h-32 border-2 border-dashed rounded flex items-center justify-center cursor-pointer hover:border-accent"
        >
          <Upload className="size-8 text-muted-foreground" />
        </div>
      )}
      <input
        ref={logoInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleLogoUpload}
      />
    </div>
  </div>
  
  {/* Optional Fields - Collapsible */}
  <Collapsible>
    <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
      <ChevronRight className="size-4" />
      Advanced Brand Configuration (Optional)
    </CollapsibleTrigger>
    <CollapsibleContent className="mt-4 space-y-4">
      <div>
        <label className="text-sm font-medium">Product Description</label>
        <Textarea
          value={brandConfig.PRODUCT_DESCRIPTION || ''}
          onChange={(e) => updateBrandConfig('PRODUCT_DESCRIPTION', e.target.value)}
          className="mt-1.5"
          rows={3}
        />
      </div>
      {/* ... other optional fields ... */}
    </CollapsibleContent>
  </Collapsible>
</section>
```

2. **Elements Section** - Keep existing but populate from template:

```tsx
<section>
  <h2 className="mb-6 text-2xl font-semibold text-foreground">Elements</h2>
  
  <div className="flex flex-wrap gap-6">
    {/* Characters */}
    {template.universe.characters.map((char) => (
      <div key={char.name} className="flex flex-col items-center gap-2">
        <Card className="w-24 h-24 relative overflow-hidden">
          <Image
            src={char.image_url}
            fill
            className="object-cover"
            alt={char.name}
          />
        </Card>
        <span className="text-xs text-center">{char.name}</span>
      </div>
    ))}
    
    {/* Locations */}
    {template.universe.universe.locations.map((loc) => (
      // Similar...
    ))}
    
    {/* Props */}
    {template.universe.universe.props.map((prop) => (
      // Similar...
    ))}
    
    {/* Brand Logo (from upload) */}
    {brandConfig.brand_logo && (
      <div className="flex flex-col items-center gap-2">
        <Card className="w-24 h-24 relative overflow-hidden">
          <Image
            src={brandConfig.brand_logo}
            fill
            className="object-contain p-2"
            alt="Brand Logo"
          />
        </Card>
        <span className="text-xs text-center">Brand Logo</span>
      </div>
    )}
  </div>
</section>
```

#### 4.1.3 Backend: Brand Logo Upload

**API Endpoint:** `/api/projects/upload-logo`

```typescript
// app/api/projects/upload-logo/route.ts
import { put } from '@vercel/blob';

export async function POST(request: Request) {
  const formData = await request.formData();
  const file = formData.get('logo') as File;
  const projectId = formData.get('projectId') as string;
  
  if (!file) {
    return Response.json({ error: 'No file provided' }, { status: 400 });
  }
  
  // Upload to Vercel Blob
  const blob = await put(
    `projects/${projectId}/brand-logo.${file.name.split('.').pop()}`,
    file,
    {
      access: 'public',
      addRandomSuffix: false,
    }
  );
  
  return Response.json({ url: blob.url });
}
```

### 4.2 Step 2: Scene Display & Editing

#### 4.2.1 Scene Tabs UI

**Reference:** Scene descriptions from `s4_revise_concept/.../revised.txt` and detailed prompts from `s7_generate_scene_prompts/.../scene_prompts.json`

**File:** `components/scenes-step.tsx`

**New Component:** `SceneEditor`

```tsx
interface SceneEditorProps {
  scene: ScenePrompt;
  sceneDescription: string; // From revised.txt
  onUpdate: (sceneNumber: number, updates: Partial<ScenePrompt>) => void;
}

function SceneEditor({ scene, sceneDescription, onUpdate }: SceneEditorProps) {
  const [activeTab, setActiveTab] = useState<'description' | 'video' | 'audio' | 'first_frame'>('description');
  
  return (
    <Card className="overflow-hidden">
      {/* Scene Header */}
      <div className="p-4 border-b flex items-center justify-between">
        <h3 className="text-lg font-semibold">Scene {scene.scene_number}</h3>
        <Badge>{scene.duration_seconds}s</Badge>
      </div>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full justify-start rounded-none border-b">
          <TabsTrigger value="description">Description</TabsTrigger>
          <TabsTrigger value="video">Video Prompt</TabsTrigger>
          <TabsTrigger value="audio">Audio</TabsTrigger>
          <TabsTrigger value="first_frame">First Frame</TabsTrigger>
        </TabsList>
        
        <TabsContent value="description" className="p-4">
          <Textarea
            value={sceneDescription}
            onChange={(e) => onUpdate(scene.scene_number, { 
              // Store in custom field for now
              description: e.target.value 
            })}
            rows={6}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground mt-2">
            High-level scene description from the creative concept
          </p>
        </TabsContent>
        
        <TabsContent value="video" className="p-4">
          <Textarea
            value={scene.video_prompt}
            onChange={(e) => onUpdate(scene.scene_number, { 
              video_prompt: e.target.value 
            })}
            rows={20}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground mt-2">
            Detailed video generation prompt (Veo 3 Fast / Sora 2)
          </p>
        </TabsContent>
        
        <TabsContent value="audio" className="p-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Background Music</label>
            <Textarea
              value={scene.audio_background}
              onChange={(e) => onUpdate(scene.scene_number, { 
                audio_background: e.target.value 
              })}
              rows={4}
              className="mt-1.5"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium">Dialogue / Narration</label>
            <Textarea
              value={scene.audio_dialogue || ''}
              onChange={(e) => onUpdate(scene.scene_number, { 
                audio_dialogue: e.target.value || null 
              })}
              rows={3}
              className="mt-1.5"
              placeholder="Speaker: [dialogue text] or leave empty for no dialogue"
            />
          </div>
        </TabsContent>
        
        <TabsContent value="first_frame" className="p-4">
          <Textarea
            value={scene.first_frame_image_prompt}
            onChange={(e) => onUpdate(scene.scene_number, { 
              first_frame_image_prompt: e.target.value 
            })}
            rows={15}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground mt-2">
            Image generation prompt for the first frame (nano-banana-pro)
          </p>
        </TabsContent>
      </Tabs>
      
      {/* Elements Used */}
      <div className="p-4 border-t bg-muted/20">
        <p className="text-xs font-medium mb-2">Elements in this scene:</p>
        <div className="flex flex-wrap gap-2">
          {scene.elements_used.characters?.map(char => (
            <Badge key={char} variant="outline">{char}</Badge>
          ))}
          {scene.elements_used.locations?.map(loc => (
            <Badge key={loc} variant="outline">{loc}</Badge>
          ))}
          {scene.elements_used.props?.map(prop => (
            <Badge key={prop} variant="outline">{prop}</Badge>
          ))}
        </div>
      </div>
    </Card>
  );
}
```

**Integration into `scenes-step.tsx`:**

```tsx
<section>
  <h2 className="mb-6 text-2xl font-semibold text-foreground">Scenes</h2>
  <div className="space-y-4">
    {scenePrompts.scenes.map((scene, index) => (
      <SceneEditor
        key={scene.scene_number}
        scene={scene}
        sceneDescription={sceneDescriptions[index] || ''}
        onUpdate={handleSceneUpdate}
      />
    ))}
  </div>
</section>
```

#### 4.2.2 Backend: Save Project Data

**API Endpoint:** `/api/projects/[projectId]/save`

```typescript
// app/api/projects/[projectId]/save/route.ts
import { sql } from '@vercel/postgres';

export async function POST(
  request: Request,
  { params }: { params: { projectId: string } }
) {
  const { projectId } = params;
  const data = await request.json();
  
  // Update project in database
  await sql`
    UPDATE projects
    SET 
      brand_config = ${JSON.stringify(data.brand_config)},
      scene_prompts = ${JSON.stringify(data.scene_prompts)},
      updated_at = NOW()
    WHERE id = ${projectId}
  `;
  
  return Response.json({ success: true });
}
```

### 4.3 Step 3: First Frame Generation

#### 4.3.1 Implementation Reference

**Python Reference:** `/Users/sanjaykarinje/git/video-gen/s8_generate_first_frames/scripts/generate_first_frames.py`

**Key Logic to Port:**

```python
# Python version (reference)
def generate_first_frame_for_scene(
    scene_prompt,
    universe_data,
    brand_config,
    reference_images_paths
):
    """Generate first frame using nano-banana-pro."""
    
    # 1. Build prompt from scene's first_frame_image_prompt
    prompt = scene_prompt["first_frame_image_prompt"]
    
    # 2. Replace brand placeholders
    prompt = prompt.replace("{BRAND_NAME}", brand_config["BRAND_NAME"])
    
    # 3. Call Replicate with reference images
    output = replicate.run(
        "lightricks/nano-banana-pro",
        input={
            "prompt": prompt,
            "reference_images": reference_images_paths,  # Attach universe element images
            "aspect_ratio": "16:9",
            "output_format": "png",
            "num_outputs": 1
        }
    )
    
    return output[0]  # Image URL
```

#### 4.3.2 Node.js Implementation

**File:** `lib/replicate/first-frames.ts`

```typescript
import Replicate from 'replicate';
import { ScenePrompt, UniverseCharacters, BrandConfig } from '@/types';

const replicate = new Replicate({
  auth: process.env.REPLICATE_API_TOKEN!,
});

interface GenerateFirstFrameOptions {
  scene: ScenePrompt;
  universe: UniverseCharacters;
  brandConfig: BrandConfig;
  universePaths: {
    charactersDir: string;
    locationsDir: string;
    propsDir: string;
  };
}

export async function generateFirstFrame({
  scene,
  universe,
  brandConfig,
  universePaths,
}: GenerateFirstFrameOptions): Promise<string> {
  console.log(`Generating first frame for scene ${scene.scene_number}...`);
  
  // 1. Collect reference images for elements used in this scene
  const referenceImages: string[] = [];
  
  // Add character images
  if (scene.elements_used.characters) {
    for (const charName of scene.elements_used.characters) {
      const char = universe.characters.find(c => c.name === charName);
      if (char?.image_url) {
        referenceImages.push(char.image_url);
      }
    }
  }
  
  // Add location images
  if (scene.elements_used.locations) {
    for (const locName of scene.elements_used.locations) {
      const loc = universe.universe.locations.find(l => l.name === locName);
      if (loc?.image_url) {
        referenceImages.push(loc.image_url);
      }
    }
  }
  
  // Add prop images
  if (scene.elements_used.props) {
    for (const propName of scene.elements_used.props) {
      const prop = universe.universe.props.find(p => p.name === propName);
      if (prop?.image_url) {
        referenceImages.push(prop.image_url);
      }
    }
  }
  
  // Add brand logo if available
  if (brandConfig.brand_logo) {
    referenceImages.push(brandConfig.brand_logo);
  }
  
  console.log(`  → Collected ${referenceImages.length} reference images`);
  
  // 2. Build prompt with brand name replacement
  let prompt = scene.first_frame_image_prompt;
  prompt = prompt.replace(/{BRAND_NAME}/g, brandConfig.BRAND_NAME);
  
  // Add brand logo context if provided
  if (brandConfig.brand_logo) {
    prompt += `\n\nBrand logo (attached in reference images): ${brandConfig.BRAND_NAME} logo`;
  }
  
  console.log(`  → Calling Replicate nano-banana-pro...`);
  
  // 3. Call Replicate
  const output = await replicate.run(
    "lightricks/nano-banana-pro",
    {
      input: {
        prompt: prompt,
        reference_images: referenceImages,
        aspect_ratio: "16:9",
        output_format: "png",
        num_outputs: 1,
        // Optional: add more control
        guidance_scale: 7.5,
        num_inference_steps: 50,
      }
    }
  ) as string[];
  
  const imageUrl = output[0];
  console.log(`  ✓ First frame generated: ${imageUrl}`);
  
  return imageUrl;
}

export async function generateAllFirstFrames(
  scenes: ScenePrompt[],
  universe: UniverseCharacters,
  brandConfig: BrandConfig,
  universePaths: GenerateFirstFrameOptions['universePaths']
): Promise<FirstFrameResult[]> {
  const results: FirstFrameResult[] = [];
  
  for (const scene of scenes) {
    try {
      const imageUrl = await generateFirstFrame({
        scene,
        universe,
        brandConfig,
        universePaths,
      });
      
      results.push({
        scene_number: scene.scene_number,
        image_url: imageUrl,
        prompt_used: scene.first_frame_image_prompt,
        created_at: new Date(),
      });
    } catch (error) {
      console.error(`Failed to generate first frame for scene ${scene.scene_number}:`, error);
      throw error;
    }
  }
  
  return results;
}
```

#### 4.3.3 API Endpoint

**File:** `app/api/projects/[projectId]/generate-first-frames/route.ts`

```typescript
import { generateAllFirstFrames } from '@/lib/replicate/first-frames';
import { sql } from '@vercel/postgres';

export async function POST(
  request: Request,
  { params }: { params: { projectId: string } }
) {
  const { projectId } = params;
  
  // 1. Load project data
  const project = await sql`
    SELECT * FROM projects WHERE id = ${projectId}
  `.then(res => res.rows[0]);
  
  if (!project) {
    return Response.json({ error: 'Project not found' }, { status: 404 });
  }
  
  // 2. Parse data
  const universe = JSON.parse(project.universe_data);
  const scenePrompts = JSON.parse(project.scene_prompts);
  const brandConfig = JSON.parse(project.brand_config);
  
  // 3. Generate first frames
  const firstFrames = await generateAllFirstFrames(
    scenePrompts.scenes,
    universe,
    brandConfig,
    {
      charactersDir: '', // Not needed with image_url in universe
      locationsDir: '',
      propsDir: '',
    }
  );
  
  // 4. Save to database
  await sql`
    UPDATE projects
    SET 
      first_frames = ${JSON.stringify(firstFrames)},
      status = 'generating_clips',
      updated_at = NOW()
    WHERE id = ${projectId}
  `;
  
  return Response.json({ firstFrames });
}
```

#### 4.3.4 UI Component

**File:** `components/scenes-step.tsx`

Add button to generate first frames:

```tsx
<div className="pb-8 flex gap-3">
  <Button variant="outline" onClick={onBack} size="lg" className="flex-1">
    Back
  </Button>
  
  {!firstFramesGenerated && (
    <Button 
      onClick={handleGenerateFirstFrames} 
      size="lg" 
      className="flex-1"
      disabled={isGeneratingFirstFrames}
    >
      {isGeneratingFirstFrames ? (
        <>
          <Loader2 className="size-4 animate-spin mr-2" />
          Generating First Frames...
        </>
      ) : (
        <>
          <Image className="size-4 mr-2" />
          Generate First Frames
        </>
      )}
    </Button>
  )}
  
  {firstFramesGenerated && (
    <Button onClick={onGenerateVideo} size="lg" className="flex-1">
      <Play className="size-4 mr-2" />
      Generate Video Clips
    </Button>
  )}
</div>
```

**Handler:**

```typescript
async function handleGenerateFirstFrames() {
  setIsGeneratingFirstFrames(true);
  
  try {
    const response = await fetch(`/api/projects/${projectId}/generate-first-frames`, {
      method: 'POST',
    });
    
    const { firstFrames } = await response.json();
    
    setFirstFrames(firstFrames);
    setFirstFramesGenerated(true);
    
    toast.success(`Generated ${firstFrames.length} first frames!`);
  } catch (error) {
    console.error('Failed to generate first frames:', error);
    toast.error('Failed to generate first frames');
  } finally {
    setIsGeneratingFirstFrames(false);
  }
}
```

### 4.4 Step 4: Video Clip Generation

#### 4.4.1 Implementation Reference

**Python Reference:** `/Users/sanjaykarinje/git/video-gen/s9_generate_video_clips/scripts/generate_video_clips.py`

**Key Logic:**

```python
# Python version (reference)
def generate_video_clip(
    scene_prompt,
    first_frame_image_url,
    reference_images,
    video_model="google/veo-3-fast"
):
    """Generate video clip using Veo 3 Fast or Sora 2."""
    
    # Determine valid durations
    if video_model == "openai/sora-2":
        valid_durations = [4, 8, 12]
    else:  # veo-3-fast
        valid_durations = [4, 6, 8]
    
    # Round to nearest valid duration
    duration = min(valid_durations, key=lambda x: abs(x - scene_prompt["duration_seconds"]))
    
    # Build input
    input_params = {
        "prompt": scene_prompt["video_prompt"],
        "first_frame_image": first_frame_image_url,
        "duration": duration,
        "aspect_ratio": "16:9",
        "reference_images": reference_images,
    }
    
    # Call Replicate
    output = replicate.run(video_model, input=input_params)
    
    return output  # Video URL
```

#### 4.4.2 Node.js Implementation

**File:** `lib/replicate/video-clips.ts`

```typescript
import Replicate from 'replicate';
import { ScenePrompt, FirstFrameResult, UniverseCharacters } from '@/types';

const replicate = new Replicate({
  auth: process.env.REPLICATE_API_TOKEN!,
});

interface GenerateVideoClipOptions {
  scene: ScenePrompt;
  firstFrame: FirstFrameResult;
  universe: UniverseCharacters;
  brandLogo?: string;
  videoModel?: 'google/veo-3-fast' | 'openai/sora-2';
}

export async function generateVideoClip({
  scene,
  firstFrame,
  universe,
  brandLogo,
  videoModel = 'google/veo-3-fast',
}: GenerateVideoClipOptions): Promise<string> {
  console.log(`Generating video for scene ${scene.scene_number}...`);
  
  // 1. Determine valid durations based on model
  const validDurations = videoModel === 'openai/sora-2' 
    ? [4, 8, 12]
    : [4, 6, 8];
  
  // Round to nearest valid duration
  const duration = validDurations.reduce((prev, curr) => 
    Math.abs(curr - scene.duration_seconds) < Math.abs(prev - scene.duration_seconds) 
      ? curr 
      : prev
  );
  
  console.log(`  → Duration: ${scene.duration_seconds}s → ${duration}s (${videoModel})`);
  
  // 2. Collect reference images
  const referenceImages: string[] = [];
  
  if (scene.elements_used.characters) {
    for (const charName of scene.elements_used.characters) {
      const char = universe.characters.find(c => c.name === charName);
      if (char?.image_url) referenceImages.push(char.image_url);
    }
  }
  
  if (scene.elements_used.locations) {
    for (const locName of scene.elements_used.locations) {
      const loc = universe.universe.locations.find(l => l.name === locName);
      if (loc?.image_url) referenceImages.push(loc.image_url);
    }
  }
  
  if (scene.elements_used.props) {
    for (const propName of scene.elements_used.props) {
      const prop = universe.universe.props.find(p => p.name === propName);
      if (prop?.image_url) referenceImages.push(prop.image_url);
    }
  }
  
  if (brandLogo) {
    referenceImages.push(brandLogo);
  }
  
  console.log(`  → Reference images: ${referenceImages.length}`);
  console.log(`  → Calling Replicate ${videoModel}...`);
  
  // 3. Call Replicate
  const output = await replicate.run(
    videoModel,
    {
      input: {
        prompt: scene.video_prompt,
        first_frame_image: firstFrame.image_url,
        duration: duration,
        aspect_ratio: "16:9",
        reference_images: referenceImages,
        // Model-specific params
        ...(videoModel === 'google/veo-3-fast' && {
          guidance_scale: 7.0,
        }),
      }
    }
  ) as string;
  
  console.log(`  ✓ Video generated: ${output}`);
  
  return output;
}

export async function generateAllVideoClips(
  scenes: ScenePrompt[],
  firstFrames: FirstFrameResult[],
  universe: UniverseCharacters,
  brandLogo?: string,
  videoModel?: 'google/veo-3-fast' | 'openai/sora-2'
): Promise<VideoClipResult[]> {
  const results: VideoClipResult[] = [];
  
  for (const scene of scenes) {
    const firstFrame = firstFrames.find(f => f.scene_number === scene.scene_number);
    
    if (!firstFrame) {
      throw new Error(`No first frame found for scene ${scene.scene_number}`);
    }
    
    try {
      const videoUrl = await generateVideoClip({
        scene,
        firstFrame,
        universe,
        brandLogo,
        videoModel,
      });
      
      results.push({
        scene_number: scene.scene_number,
        video_url: videoUrl,
        duration_seconds: scene.duration_seconds,
        prompt_used: scene.video_prompt,
        created_at: new Date(),
      });
    } catch (error) {
      console.error(`Failed to generate video for scene ${scene.scene_number}:`, error);
      throw error;
    }
  }
  
  return results;
}
```

#### 4.4.3 API Endpoint

**File:** `app/api/projects/[projectId]/generate-clips/route.ts`

```typescript
import { generateAllVideoClips } from '@/lib/replicate/video-clips';
import { sql } from '@vercel/postgres';

export async function POST(
  request: Request,
  { params }: { params: { projectId: string } }
) {
  const { projectId } = params;
  const { videoModel } = await request.json();
  
  // 1. Load project
  const project = await sql`
    SELECT * FROM projects WHERE id = ${projectId}
  `.then(res => res.rows[0]);
  
  if (!project) {
    return Response.json({ error: 'Project not found' }, { status: 404 });
  }
  
  // 2. Parse data
  const universe = JSON.parse(project.universe_data);
  const scenePrompts = JSON.parse(project.scene_prompts);
  const firstFrames = JSON.parse(project.first_frames);
  const brandConfig = JSON.parse(project.brand_config);
  
  // 3. Generate video clips
  const videoClips = await generateAllVideoClips(
    scenePrompts.scenes,
    firstFrames,
    universe,
    brandConfig.brand_logo,
    videoModel || 'google/veo-3-fast'
  );
  
  // 4. Save to database
  await sql`
    UPDATE projects
    SET 
      video_clips = ${JSON.stringify(videoClips)},
      status = 'merging',
      updated_at = NOW()
    WHERE id = ${projectId}
  `;
  
  return Response.json({ videoClips });
}
```

#### 4.4.4 UI Component

**File:** `components/video-editor-step.tsx`

Update to trigger video generation and show progress:

```tsx
export function VideoEditorStep({ 
  scenes, 
  onExport, 
  onBack,
  projectId 
}: VideoEditorStepProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [videoClips, setVideoClips] = useState<VideoClipResult[]>([]);
  
  async function handleGenerateClips() {
    setIsGenerating(true);
    setProgress(0);
    
    try {
      const response = await fetch(`/api/projects/${projectId}/generate-clips`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          videoModel: 'google/veo-3-fast', // or let user choose
        }),
      });
      
      const { videoClips } = await response.json();
      
      setVideoClips(videoClips);
      setProgress(100);
      
      toast.success(`Generated ${videoClips.length} video clips!`);
    } catch (error) {
      console.error('Failed to generate clips:', error);
      toast.error('Failed to generate video clips');
    } finally {
      setIsGenerating(false);
    }
  }
  
  return (
    <div className="h-full flex flex-col">
      {/* Video previews */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-2 gap-4">
          {videoClips.map((clip) => (
            <Card key={clip.scene_number}>
              <div className="aspect-video bg-black relative">
                <video
                  src={clip.video_url}
                  controls
                  className="w-full h-full"
                />
              </div>
              <div className="p-3">
                <p className="font-medium">Scene {clip.scene_number}</p>
                <p className="text-sm text-muted-foreground">{clip.duration_seconds}s</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
      
      {/* Actions */}
      <div className="border-t p-6 flex gap-3">
        <Button variant="outline" onClick={onBack} size="lg">
          Back
        </Button>
        
        {videoClips.length === 0 && (
          <Button 
            onClick={handleGenerateClips} 
            size="lg" 
            className="flex-1"
            disabled={isGenerating}
          >
            {isGenerating ? (
              <>
                <Loader2 className="size-4 animate-spin mr-2" />
                Generating Videos... {progress}%
              </>
            ) : (
              <>
                <Film className="size-4 mr-2" />
                Generate Video Clips
              </>
            )}
          </Button>
        )}
        
        {videoClips.length > 0 && (
          <Button onClick={onExport} size="lg" className="flex-1">
            <Download className="size-4 mr-2" />
            Merge & Export Final Video
          </Button>
        )}
      </div>
    </div>
  );
}
```

### 4.5 Step 5: Merge Clips & Final Export

#### 4.5.1 Implementation Reference

**Python Reference:** `/Users/sanjaykarinje/git/video-gen/s10_merge_clips/scripts/merge_video_clips_ffmpeg.py`

**Key Logic:**

```python
# Python version (reference)
def merge_video_clips(video_clip_urls, output_path):
    """Merge video clips using FFmpeg."""
    
    # 1. Download all clips
    clip_files = []
    for i, url in enumerate(video_clip_urls):
        clip_path = f"/tmp/clip_{i}.mp4"
        download_file(url, clip_path)
        clip_files.append(clip_path)
    
    # 2. Create FFmpeg concat file
    concat_file = "/tmp/concat_list.txt"
    with open(concat_file, 'w') as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")
    
    # 3. Run FFmpeg
    subprocess.run([
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ])
    
    return output_path
```

#### 4.5.2 Node.js Implementation

**File:** `lib/video/merge-clips.ts`

```typescript
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';
import fetch from 'node-fetch';
import { put } from '@vercel/blob';

const execAsync = promisify(exec);

interface VideoClip {
  scene_number: number;
  video_url: string;
  duration_seconds: number;
}

async function downloadFile(url: string, outputPath: string): Promise<void> {
  const response = await fetch(url);
  const buffer = await response.buffer();
  await fs.writeFile(outputPath, buffer);
}

export async function mergeVideoClips(
  clips: VideoClip[],
  projectId: string
): Promise<string> {
  console.log(`Merging ${clips.length} video clips...`);
  
  const tmpDir = `/tmp/${projectId}`;
  await fs.mkdir(tmpDir, { recursive: true });
  
  try {
    // 1. Download all clips
    const clipPaths: string[] = [];
    for (let i = 0; i < clips.length; i++) {
      const clip = clips[i];
      const clipPath = path.join(tmpDir, `clip_${i}.mp4`);
      
      console.log(`  → Downloading clip ${i + 1}/${clips.length}...`);
      await downloadFile(clip.video_url, clipPath);
      clipPaths.push(clipPath);
    }
    
    // 2. Create concat file
    const concatFilePath = path.join(tmpDir, 'concat_list.txt');
    const concatContent = clipPaths
      .map(p => `file '${p}'`)
      .join('\n');
    await fs.writeFile(concatFilePath, concatContent);
    
    // 3. Run FFmpeg
    const outputPath = path.join(tmpDir, 'final_video.mp4');
    console.log(`  → Running FFmpeg to merge clips...`);
    
    await execAsync([
      'ffmpeg',
      '-f concat',
      '-safe 0',
      `-i ${concatFilePath}`,
      '-c copy',
      outputPath
    ].join(' '));
    
    console.log(`  ✓ Merged video created: ${outputPath}`);
    
    // 4. Upload to Vercel Blob
    console.log(`  → Uploading to Vercel Blob...`);
    const videoBuffer = await fs.readFile(outputPath);
    const blob = await put(
      `projects/${projectId}/final-video.mp4`,
      videoBuffer,
      {
        access: 'public',
        addRandomSuffix: false,
      }
    );
    
    console.log(`  ✓ Uploaded: ${blob.url}`);
    
    // 5. Cleanup
    await fs.rm(tmpDir, { recursive: true, force: true });
    
    return blob.url;
  } catch (error) {
    // Cleanup on error
    await fs.rm(tmpDir, { recursive: true, force: true });
    throw error;
  }
}
```

#### 4.5.3 API Endpoint

**File:** `app/api/projects/[projectId]/merge-clips/route.ts`

```typescript
import { mergeVideoClips } from '@/lib/video/merge-clips';
import { sql } from '@vercel/postgres';

export async function POST(
  request: Request,
  { params }: { params: { projectId: string } }
) {
  const { projectId } = params;
  
  // 1. Load project
  const project = await sql`
    SELECT * FROM projects WHERE id = ${projectId}
  `.then(res => res.rows[0]);
  
  if (!project) {
    return Response.json({ error: 'Project not found' }, { status: 404 });
  }
  
  // 2. Parse video clips
  const videoClips = JSON.parse(project.video_clips);
  
  if (!videoClips || videoClips.length === 0) {
    return Response.json({ error: 'No video clips to merge' }, { status: 400 });
  }
  
  // 3. Merge clips
  const finalVideoUrl = await mergeVideoClips(videoClips, projectId);
  
  // 4. Save to database
  await sql`
    UPDATE projects
    SET 
      final_video = ${finalVideoUrl},
      status = 'complete',
      updated_at = NOW()
    WHERE id = ${projectId}
  `;
  
  return Response.json({ finalVideoUrl });
}
```

#### 4.5.4 UI Component

**File:** `components/video-step.tsx`

```tsx
export function VideoStep({ onStartOver, projectId }: VideoStepProps) {
  const [finalVideoUrl, setFinalVideoUrl] = useState<string | null>(null);
  const [isMerging, setIsMerging] = useState(false);
  
  useEffect(() => {
    // Auto-merge on mount
    handleMergeClips();
  }, []);
  
  async function handleMergeClips() {
    setIsMerging(true);
    
    try {
      const response = await fetch(`/api/projects/${projectId}/merge-clips`, {
        method: 'POST',
      });
      
      const { finalVideoUrl } = await response.json();
      
      setFinalVideoUrl(finalVideoUrl);
      toast.success('Final video ready!');
    } catch (error) {
      console.error('Failed to merge clips:', error);
      toast.error('Failed to merge video clips');
    } finally {
      setIsMerging(false);
    }
  }
  
  return (
    <div className="h-full flex items-center justify-center p-6">
      <Card className="max-w-4xl w-full">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-4">Final Video</h2>
          
          {isMerging && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-12 animate-spin text-accent" />
              <p className="ml-4 text-lg">Merging video clips...</p>
            </div>
          )}
          
          {finalVideoUrl && (
            <>
              <div className="aspect-video bg-black rounded-lg overflow-hidden mb-6">
                <video
                  src={finalVideoUrl}
                  controls
                  autoPlay
                  className="w-full h-full"
                />
              </div>
              
              <div className="flex gap-3">
                <Button
                  onClick={() => window.open(finalVideoUrl, '_blank')}
                  size="lg"
                  className="flex-1"
                >
                  <Download className="size-4 mr-2" />
                  Download Video
                </Button>
                
                <Button
                  onClick={onStartOver}
                  variant="outline"
                  size="lg"
                >
                  Create Another
                </Button>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
```

---

## 5. Database Schema

**File:** `schema.sql`

```sql
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  template_id VARCHAR(255) NOT NULL,
  
  -- Stored as JSON
  brand_config JSONB NOT NULL,
  universe_data JSONB NOT NULL,
  scene_prompts JSONB NOT NULL,
  first_frames JSONB,
  video_clips JSONB,
  
  -- Final output
  final_video TEXT,
  
  -- Status tracking
  status VARCHAR(50) DEFAULT 'draft',
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created_at ON projects(created_at DESC);
```

---

## 6. Environment Variables

**File:** `.env.local`

```bash
# Replicate API
REPLICATE_API_TOKEN=r8_xxxxx

# Vercel Storage
BLOB_READ_WRITE_TOKEN=vercel_blob_xxxxx
POSTGRES_URL=postgres://xxxxx

# Optional: OpenAI for future features
OPENAI_API_KEY=sk-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

---

## 7. Implementation Checklist

### Phase 1: Foundation
- [ ] Set up Vercel Postgres database
- [ ] Set up Vercel Blob storage
- [ ] Create database schema
- [ ] Implement template discovery API
- [ ] Implement template image serving API

### Phase 2: Project Setup
- [ ] Create project creation flow
- [ ] Implement brand logo upload
- [ ] Build brand configuration UI (with collapsible advanced)
- [ ] Load template data into project

### Phase 3: Scene Editing
- [ ] Build scene editor with 4 tabs (description, video, audio, first_frame)
- [ ] Implement scene update API
- [ ] Add save/autosave functionality

### Phase 4: First Frame Generation
- [ ] Port first frame generation logic to Node.js
- [ ] Create first frame generation API
- [ ] Add UI with progress tracking
- [ ] Display generated first frames in UI

### Phase 5: Video Generation
- [ ] Port video generation logic to Node.js
- [ ] Create video clip generation API
- [ ] Add UI with progress tracking
- [ ] Display video clips with preview

### Phase 6: Final Merge
- [ ] Implement FFmpeg merge logic
- [ ] Create merge API endpoint
- [ ] Build final video preview UI
- [ ] Add download functionality

### Phase 7: Polish
- [ ] Error handling and retry logic
- [ ] Loading states and progress bars
- [ ] Toast notifications
- [ ] Responsive design
- [ ] Performance optimization

---

## 8. Code Snippets & References

### 8.1 Template JSON Example

**Location:** `/Users/sanjaykarinje/git/video-gen/s5_generate_universe/outputs/sunvue_1121_0921/sunvue_focus_finds_you_revised/sunvue_focus_finds_you_revised_universe_characters.json`

### 8.2 Scene Prompts JSON Example

**Location:** `/Users/sanjaykarinje/git/video-gen/s7_generate_scene_prompts/outputs/sunvue_1120_2106/sunvue_transformation_instant_upgrade_generic_gpt_5.1/sunvue_transformation_instant_upgrade_generic_gpt_5.1_scene_prompts.json`

### 8.3 Brand Config JSON Example

**Location:** `/Users/sanjaykarinje/git/video-gen/s1_generate_concepts/inputs/configs/sunglasses.json`

### 8.4 Python Generate Scene Prompts Reference

**Location:** `/Users/sanjaykarinje/git/video-gen/s7_generate_scene_prompts/scripts/generate_scene_prompts.py`

Key functions to port:
- `generate_scene_prompts()` - Main orchestration
- `call_anthropic_with_caching()` - API call with caching
- Prompt building logic (lines 385-612)

---

## 9. Success Criteria

1. ✅ User can select a template and see universe elements
2. ✅ User can upload brand logo and configure brand details
3. ✅ User can view and edit scene descriptions across 4 tabs
4. ✅ System generates first frames using Replicate nano-banana-pro
5. ✅ System generates video clips using Replicate Veo 3 Fast
6. ✅ System merges clips into final video
7. ✅ All intermediate outputs stored in Vercel Blob/Postgres
8. ✅ User can download final video

---

## 10. Future Enhancements

1. Real-time collaboration on projects
2. Audio generation integration (ElevenLabs/Suno)
3. Advanced video editing (trim, reorder scenes)
4. Custom template creation
5. Batch project generation
6. Analytics and usage tracking

