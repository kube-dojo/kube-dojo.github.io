---
title: "Модуль 1.2: Поглиблене вивчення Custom Resource Definitions"
slug: "uk/k8s/extending/module-1.2-crds-advanced"
sidebar:
  order: 3
revision_pending: false
en_commit: "26342c0ca358c92129aa43ee22f0519a67887176"
en_file: "src/content/docs/k8s/extending/module-1.2-crds-advanced.md"
calque_review:
  reviewed_at: "2026-06-22"
  detector_version: "v2"
  status: "reviewed"
  flags_resolved: 1
  content_sha: "6263cceb57713e4b09bcc63052377646b57cc5090a056ab55e8966bdbc34c61a"
---

> **Складність**: `[СЕРЕДНЯ]` — визначення власних API Kubernetes
>
> **Час на проходження**: 3 години
>
> **Передумови**: Модуль 1.1 (Поглиблене вивчення API), знайомство з YAML та JSON Schema

---

## Результати навчання

Після завершення цього модуля ви зможете:

1. **Спроєктувати** схему CRD зі структурною валідацією, правилами CEL та значеннями за замовчуванням, що відхиляють некоректні дані на етапі допуску (admission).
2. **Впровадити** версіонування CRD зі версіями зберігання (storage versions) та вебхуками конвертації, щоб об'єкти стилю `v1alpha1` та `v1` безпечно співіснували.
3. **Налаштувати** субресурси, додаткові стовпці виводу (printer columns) та шляхи масштабування, щоб `kubectl` забезпечував корисну операційну поведінку для власних ресурсів.
4. **Діагностувати** збої валідації CRD, несподіванки з відсіканням (pruning) полів та проблеми розбіжності версій (version skew), використовуючи виявлення API (discovery), запити в режимі dry-run та явне читання конкретних версій.

---

## Чому цей модуль важливий

Гіпотетичний сценарій: ваша платформена команда публікує API `BackupPolicy`, щоб прикладні команди могли описувати розклади резервного копіювання, не вивчаючи внутрішню будову контролера бекапів. Перші кілька маніфестів працюють, але потім одна команда надсилає рядок розкладу, який контролер не може розпарсити, інша команда встановлює період зберігання у від'ємне число, а старе автоматизоване завдання продовжує створювати ресурси `v1alpha1` після того, як ви вже навчили новіших клієнтів про `v1beta1`. Жодна з цих помилок не повинна вимагати падіння контролера, перш ніж хтось її помітить.

CRD — це спосіб, у який Kubernetes дозволяє додати до API новий іменник, не латаючи сам API-сервер. Коли ви встановлюєте такі системи, як Istio, Argo CD, cert-manager або Prometheus Operator, вони реєструють типи ресурсів на кшталт `VirtualService`, `Application`, `Certificate` та `ServiceMonitor`, щоб кластер міг зберігати та обслуговувати специфічні для домену об'єкти через ту саму машинерію виявлення, авторизації, допуску, спостереження (watch) та зберігання, яку використовують вбудовані ресурси. Це потужно, але водночас означає, що ваш CRD стає публічним контрактом тієї миті, коли інші команди починають писати під нього YAML.

Аналогія з таблицею бази даних корисна, доки ви не сприймаєте її надто буквально. CRD схожий на інструкцію `CREATE TABLE`, бо він оголошує назву, групу, поля та правила валідації для нової колекції записів. Kubernetes потім обробляє створення, читання, оновлення, видалення, спостереження, авторизацію та збереження в etcd для цих записів, тоді як ваш контролер зосереджується на узгодженні бажаного стану з реальною інфраструктурою. Проте, на відміну від простої таблиці, API Kubernetes також потребує узгодження версій, встановлення значень за замовчуванням, відсікання полів, субресурсів, семантики server-side apply та орієнтованого на користувача виводу виявлення, який має пережити роки існування клієнтів.

Цей модуль навчає форми такого контракту. Ви почнете з анатомії CRD, перейдете до структурної валідації OpenAPI та правил CEL, а потім додасте версіонування, конвертацію, відокремлення статусу, підтримку масштабування та стовпці виводу. Практична вправа зведе ці частини разом у API `BackupPolicy`, що відхиляє некоректні дані на етапі допуску і дає операторам достатньо інформації для діагностики поведінки без читання сирого JSON.

---

## Основний зміст

### Анатомія CRD та контракти іменування

CRD починається з іменування, а іменування в Kubernetes не є косметичним. Група, kind, назва у множині, назва в однині, короткі назви, категорії та область видимості визначають, як ресурс з'являється у виявленні, REST-шляхах, правилах RBAC та повсякденних робочих процесах `kubectl`. Якщо два постачальники обирають однакову групу та назву в множині, кластер не має нейтрального способу обслуговувати обидва API під одним шляхом, тому іменування у зворотному порядку домену (reverse-domain) є практичним механізмом уникнення колізій, а не вподобанням стилю.

Поле `metadata.name` CRD має бути назвою ресурсу у множині, за якою йде група API. Це дає Kubernetes стабільний REST-шлях колекції для ваших об'єктів, наприклад `/apis/data.kubedojo.io/v1alpha1/namespaces/default/backuppolicies`. Поле `kind` залишається в однині та в PascalCase, бо це назва типу, яку користувачі бачать усередині маніфестів, тоді як `plural` та `singular` — це назви в нижньому регістрі, які використовуються виявленням та клієнтами командного рядка. Область видимості так само важлива: оберіть `Namespaced` для ресурсів, що належать команді, навантаженню, орендарю (tenant) чи межі простору імен, і зарезервуйте `Cluster` для ресурсів, які справді представляють політику рівня кластера.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backuppolicies.data.kubedojo.io    # plural.group
spec:
  group: data.kubedojo.io                   # API group
  names:
    kind: BackupPolicy                      # PascalCase
    listKind: BackupPolicyList
    plural: backuppolicies                  # URL path
    singular: backuppolicy                  # kubectl alias
    shortNames:
    - bp                                    # kubectl shorthand
    categories:
    - all                                   # appears in `kubectl get all`
  scope: Namespaced                         # or Cluster
  versions:
  - name: v1alpha1
    served: true                            # API Server serves this version
    storage: true                           # Stored in etcd as this version
    schema:
      openAPIV3Schema:                      # Validation schema
        type: object
        properties:
          spec:
            type: object
            properties:
              schedule:
                type: string
              retention:
                type: integer
```

Наведений вище приклад навмисно невеликий, але він уже демонструє найважливіше рішення: ви визначаєте API, а не просто шматок YAML. `BackupPolicy` належить до групи `data.kubedojo.io`, тож адміністратор може писати правила RBAC проти цієї групи, політика допуску може зіставлятися з цією групою, а клієнт може виявити обслуговувані версії. Навіть коли контролер ще не написаний, API-сервер може валідувати, зберігати, перелічувати, спостерігати та видаляти об'єкти цього kind.

| Поле | Конвенція | Приклад |
|-------|-----------|---------|
| `group` | Зворотний домен, що належить вам | `data.kubedojo.io` |
| `kind` | PascalCase, однина | `BackupPolicy` |
| `plural` | нижній регістр, множина | `backuppolicies` |
| `singular` | нижній регістр, однина | `backuppolicy` |
| `shortNames` | Скорочення з 1-4 літер | `bp` |
| `metadata.name` CRD | `{plural}.{group}` | `backuppolicies.data.kubedojo.io` |

Ніколи не використовуйте `k8s.io`, `kubernetes.io` чи іншу групу, якою ви не володієте. Ці назви зарезервовані для основних API Kubernetes або для інших власників, і колізія змушує користувачів обирати між конкурентними визначеннями. Група зі зворотним доменом сама по собі не є межею безпеки, але вона дає людям та автоматизації чіткий сигнал про власника, коли вони перевіряють вивід виявлення або переглядають маніфест.

Зупиніться та спрогнозуйте: як ви думаєте, що станеться, якщо два оператори обидва спробують створити CRD, чиє `metadata.name` дорівнює `backuppolicies.data.kubedojo.io`, але чиї схеми описують різні поля? API-сервер прийме лише один об'єкт під цією назвою, і кожен клієнт, що використовує цю групу та множину, буде прив'язаний до тієї схеми, яка перемогла. Саме тому іменування є частиною проєктування API, а не паперовою формальністю на початку файлу.

### Структурні схеми, відсікання, значення за замовчуванням та CEL

Kubernetes вимагає, щоб CRD у `apiextensions.k8s.io/v1` використовували структурні схеми OpenAPI v3. Структурна означає, що API-сервер може визначити тип і форму кожного поля, не виконуючи довільний код і не розв'язуючи неоднозначні гілки схеми. Ця властивість дозволяє API-серверу відсікати невідомі поля, застосовувати значення за замовчуванням, публікувати OpenAPI для клієнтів, обчислювати керовані поля (managed fields) для server-side apply та відхиляти некоректні дані до того, як об'єкт потрапить до etcd чи вашого контролера.

Найпоширеніша помилка — ставитися до валідації як до чогось, що контролер може прибрати пізніше. Це робить кожен поганий маніфест проблемою узгодження і означає, що некоректний стан може вже зберігатися та спостерігатися іншими компонентами, перш ніж ваш контролер відреагує. Сильні схеми CRD переносять якомога більше валідації на етап допуску, де користувачі отримують синхронні помилки, автоматизація може швидко завершитися збоєм, а контролери можуть припускати вужчу, безпечнішу область вхідних даних.

Кожне поле повинно мати явний `type`, а важливі поля повинні використовувати `required`, `minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `enum` та обмежені розміри колекцій. Значення за замовчуванням застосовуються перед валідацією, тож правило, що посилається на поле зі значенням за замовчуванням, бачить це значення. Невідомі поля відсікаються, якщо ви навмисно не зберігаєте їх у конкретному піддереві, що корисно для конфігурації плагінів, але небезпечно, якщо ви використовуєте це, щоб уникнути моделювання свого API.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
    shortNames:
    - wa
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        description: "WebApp defines a web application deployment."
        required:
        - spec
        properties:
          spec:
            type: object
            description: "WebAppSpec defines the desired state."
            required:
            - image
            - replicas
            properties:
              image:
                type: string
                description: "Container image in registry/repo:tag format."
                pattern: '^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)*:[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$'
                minLength: 3
                maxLength: 255
              replicas:
                type: integer
                description: "Number of desired pod replicas."
                minimum: 1
                maximum: 100
                default: 2
              port:
                type: integer
                description: "Container port to expose."
                minimum: 1
                maximum: 65535
                default: 8080
              env:
                type: array
                description: "Environment variables for the container."
                maxItems: 50
                items:
                  type: object
                  required:
                  - name
                  - value
                  properties:
                    name:
                      type: string
                      description: "Environment variable name."
                      pattern: '^[A-Z_][A-Z0-9_]*$'
                      minLength: 1
                      maxLength: 128
                    value:
                      type: string
                      description: "Environment variable value."
                      maxLength: 4096
              resources:
                type: object
                description: "Resource requirements."
                properties:
                  cpuLimit:
                    type: string
                    description: "CPU limit (e.g., 500m, 1)."
                    pattern: '^[0-9]+m?$'
                    default: "500m"
                  memoryLimit:
                    type: string
                    description: "Memory limit (e.g., 128Mi, 1Gi)."
                    pattern: '^[0-9]+(Ki|Mi|Gi|Ti)?$'
                    default: "256Mi"
              ingress:
                type: object
                description: "Ingress configuration."
                properties:
                  enabled:
                    type: boolean
                    default: false
                  host:
                    type: string
                    description: "Hostname for ingress."
                    pattern: '^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$'
                  path:
                    type: string
                    default: "/"
                  tlsEnabled:
                    type: boolean
                    default: false
              healthCheck:
                type: object
                description: "Health check configuration."
                properties:
                  path:
                    type: string
                    description: "HTTP path for health checks."
                    default: "/healthz"
                  intervalSeconds:
                    type: integer
                    minimum: 5
                    maximum: 300
                    default: 10
                  timeoutSeconds:
                    type: integer
                    minimum: 1
                    maximum: 60
                    default: 3
          status:
            type: object
            description: "WebAppStatus defines the observed state."
            properties:
              readyReplicas:
                type: integer
                description: "Number of pods that are ready."
              availableReplicas:
                type: integer
                description: "Number of pods available for service."
              conditions:
                type: array
                description: "Current conditions of the WebApp."
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                      description: "Condition type."
                    status:
                      type: string
                      description: "Condition status."
                      enum:
                      - "True"
                      - "False"
                      - "Unknown"
                    reason:
                      type: string
                      description: "Machine-readable reason."
                    message:
                      type: string
                      description: "Human-readable message."
                    lastTransitionTime:
                      type: string
                      format: date-time
                      description: "When the condition last changed."
              observedGeneration:
                type: integer
                format: int64
                description: "Generation observed by the controller."
```

Ця схема робить більше, ніж описує документацію для людей. Вона відхиляє образи, що не відповідають очікуваному патерну реєстру та тегу, обмежує кількість реплік, встановлює значення за замовчуванням для поширених полів, обмежує розміри колекцій та звужує статус condition до відомих значень. API-сервер може повернути помилку валідації, перш ніж контролер побачить некоректний об'єкт, що зменшує кількість гілок у контролері та покращує зворотний зв'язок для користувачів, які пишуть маніфести.

Зупиніться та спрогнозуйте: якщо користувач надсилає `WebApp` зі змінною середовища з назвою `1_INVALID`, яке саме правило схеми відхиляє її та коли відбувається відхилення? Поле `pattern` під `spec.env.items.properties.name` відхиляє значення під час допуску на API-сервері, перш ніж об'єкт буде збережено. Контролеру ніколи не потрібен особливий випадок для цієї некоректної змінної середовища, бо некоректний об'єкт ніколи не стає збереженим станом кластера.

| Ключове слово | Застосовується до | Приклад |
|---------|-----------|---------|
| `minimum` / `maximum` | integer, number | `minimum: 1` |
| `exclusiveMinimum` / `exclusiveMaximum` | integer, number | `exclusiveMinimum: true` |
| `minLength` / `maxLength` | string | `maxLength: 253` |
| `pattern` | string | `pattern: '^[a-z]+$'` |
| `enum` | будь-який | `enum: ["debug", "info", "warn"]` |
| `minItems` / `maxItems` | array | `maxItems: 10` |
| `uniqueItems` | array | `uniqueItems: true` |
| `required` | object | `required: ["name"]` |
| `default` | будь-який | `default: 3` |
| `format` | string | `format: date-time` |
| `nullable` | будь-який | `nullable: true` |

Kubernetes також додає поля-розширення до OpenAPI, щоб власні API могли поводитися більше як вбудовані. Розширення для списків та мап повідомляють server-side apply, чи є колекція атомарною, множиноподібною (set-like) або мапоподібною (map-like), що змінює спосіб злиття змін кількома менеджерами полів. Розширення валідації дозволяють приєднати вирази CEL там, де простих обмежень для окремого поля недостатньо, включно з перевірками незмінності та зв'язками між сусідніми полями.

```yaml
properties:
  metadata:
    type: object
    properties:
      name:
        type: string
        # Validate like a Kubernetes name
        x-kubernetes-validations:
        - rule: "self.matches('^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')"
          message: "must be a valid Kubernetes name"

  ports:
    type: array
    x-kubernetes-list-type: map
    x-kubernetes-list-map-keys:
    - containerPort
    items:
      type: object
      properties:
        containerPort:
          type: integer
        protocol:
          type: string

  labels:
    type: object
    additionalProperties:
      type: string
    x-kubernetes-map-type: granular   # SSA tracks individual keys

  immutableField:
    type: string
    x-kubernetes-validations:
    - rule: "self == oldSelf"
      message: "field is immutable once set"
```

Приклад із `ports` — це практичне рішення для server-side apply. Без мапоподібної семантики менеджер, що володіє одним елементом списку, може конфліктувати або перезаписувати інший менеджер, що володіє іншим елементом, бо весь список може розглядатися як одне поле. З `x-kubernetes-list-type: map` та стабільним ключем Kubernetes може міркувати про окремі записи, що ближче до того, як оператори очікують поведінки списків портів, conditions та іменованих правил.

Правила CEL найкраще використовувати для зв'язків, які OpenAPI не виражає чисто, як-от `minReplicas`, що має бути меншим або рівним `maxReplicas`, або вимога хоста для ingress, коли увімкнено TLS. Правила валідації CEL через `x-kubernetes-validations` досягли статусу GA у Kubernetes 1.29, тож вони є надійним рівнем, що примусово виконується сервером на кожному підтримуваному кластері, а не альфа-зручністю. Тримайте правила CEL невеликими, детермінованими та безпосередньо прив'язаними до поля, що валідується. Якщо правило потребує мережевих викликів, великих пошуків чи бізнес-політики, що часто змінюється, використовуйте натомість вебхук допуску або логіку контролера.

```yaml
spec:
  type: object
  x-kubernetes-validations:
  - rule: "self.minReplicas <= self.maxReplicas"
    message: "minReplicas must not exceed maxReplicas"
    fieldPath: ".minReplicas"
  - rule: "self.replicas >= self.minReplicas && self.replicas <= self.maxReplicas"
    message: "replicas must be between minReplicas and maxReplicas"
  - rule: "!has(self.ingress) || !self.ingress.tlsEnabled || self.ingress.host != ''"
    message: "host is required when TLS is enabled"
  properties:
    minReplicas:
      type: integer
    maxReplicas:
      type: integer
    replicas:
      type: integer
    ingress:
      type: object
      properties:
        tlsEnabled:
          type: boolean
        host:
          type: string
```

Перш ніж це запустити, який вивід ви очікуєте від dry-run на стороні сервера, коли `minReplicas` більше за `maxReplicas`? Вам слід очікувати помилку допуску з повідомленням від правила CEL, а не збережений об'єкт, який контролер пізніше позначить як невдалий. Ця різниця важлива, бо помилки допуску є дешевими, негайними та видимими для інструмента, що надіслав маніфест.

| Вираз | Опис |
|-----------|------------|
| `self` | Поточне значення поля |
| `oldSelf` | Попереднє значення (для валідації оновлень) |
| `self.field` | Доступ до підполя |
| `self.list.exists(x, x.name == 'foo')` | Перевірити, чи відповідає будь-який елемент |
| `self.list.all(x, x.port > 0)` | Перевірити, чи відповідають усі елементи |
| `self.matches('^[a-z]+$')` | Зіставлення з регулярним виразом |
| `size(self) <= 10` | Перевірка розміру колекції/рядка |
| `has(self.optionalField)` | Перевірити, чи встановлено необов'язкове поле |

### Версіонування, конвертація та міграція зберігання

Перша версія CRD рідко буває остаточною. Поля перейменовуються, статус збагачується, вкладені об'єкти замінюють пласкі рядки, а клієнти продовжують існувати після того, як платформена команда вже рушила далі. Kubernetes вирішує це, дозволяючи CRD обслуговувати кілька версій, обираючи рівно одну версію зберігання для etcd. Обслуговувані версії — це форми API, які клієнти можуть запитувати, тоді як версія зберігання — це внутрішнє збережене представлення.

Версіонування не є дозволом робити довільні зворотно несумісні зміни в надії, що клієнти адаптуються. Хороший план версій CRD починається з рішення, які зміни є додатковими (additive), а які потребують конвертації. Додавання необов'язкового поля зазвичай легке, бо старіші клієнти можуть його ігнорувати, але перейменування `port` на `ports` чи заміна `target: "deployment/web"` на структурований селектор змінює значення. Коли версії структурно відрізняються, API-серверу потрібен вебхук конвертації, що може перекладати між версіями на шляхах читання та запису.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true       # Clients can read/write this version
    storage: false      # NOT the storage version
    deprecated: true    # Show deprecation warning
    deprecationWarning: "apps.kubedojo.io/v1alpha1 WebApp is deprecated; use v1beta1"
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              image:
                type: string
              replicas:
                type: integer
              port:
                type: integer
          status:
            type: object
            properties:
              readyReplicas:
                type: integer

  - name: v1beta1
    served: true       # Clients can read/write this version
    storage: true       # THIS version is stored in etcd
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required:
            - image
            properties:
              image:
                type: string
              replicas:
                type: integer
                minimum: 1
                maximum: 100
                default: 2
              ports:                  # Renamed from 'port' to 'ports' (array)
                type: array
                items:
                  type: object
                  properties:
                    name:
                      type: string
                    containerPort:
                      type: integer
                    protocol:
                      type: string
                      enum: ["TCP", "UDP"]
                      default: "TCP"
              resources:              # New field in v1beta1
                type: object
                properties:
                  cpuLimit:
                    type: string
                  memoryLimit:
                    type: string
          status:
            type: object
            properties:
              readyReplicas:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type:
                      type: string
                    status:
                      type: string
```

У цьому прикладі обидві версії залишаються обслуговуваними, але зберігається лише `v1beta1`. Оскільки ці дві версії структурно відрізняються, автоматична конвертація між ними потребує вебхука конвертації (`strategy: Webhook`, показано далі). За стратегією за замовчуванням `None` API-сервер лише переписує мітку `apiVersion` та копіює поля як є, що безпечно ЛИШЕ тоді, коли схеми сумісні. Клієнт може створити об'єкт `v1alpha1`, і API-сервер збереже його у версії зберігання; під час читання він повертає збережені поля під запитуваною міткою версії, не перекладаючи `port` на `ports`, якщо тільки вебхук не виконає це зіставлення.

Існує дві стратегії конвертації. Стратегія `None` фактично є no-op і безпечна лише тоді, коли схеми достатньо сумісні, щоб той самий об'єкт можна було представити в різних версіях без семантичного перекладу. Стратегія `Webhook` надсилає огляди конвертації (conversion reviews) до сервісу, який ви експлуатуєте, і цей сервіс має достатньо коректно обробляти кожну підтримувану пару версій, щоб старі та нові клієнти бачили стабільне значення.

```yaml
spec:
  conversion:
    strategy: Webhook
    webhook:
      conversionReviewVersions: ["v1"]
      clientConfig:
        service:
          namespace: webapp-system
          name: webapp-webhook
          path: /convert
          port: 443
        caBundle: <base64-encoded-CA-cert>
```

Вебхуки конвертації перебувають на чутливому шляху запитів. Якщо вебхук недоступний, повільний або повертає неузгоджені об'єкти, читання та запис для відповідних версій можуть зазнавати збоїв або дивувати клієнтів. Ставтеся до коду конвертації як до коду сумісності API: покрийте його тестами, тримайте його детермінованим, зберігайте невідоме значення, коли це можливо, і розгортайте його перед перемиканням версій зберігання чи оголошенням старіших обслуговуваних версій застарілими.

Зміна версії зберігання не переписує миттєво кожен наявний об'єкт у etcd. Наявні об'єкти залишаються збереженими у старішому представленні, доки їх не перепишуть, тоді як читання може конвертувати їх на льоту. Така лінива поведінка уникає миттєвого перезапису всього кластера, але також означає, що вам потрібен продуманий план міграції зберігання, коли ви хочете, щоб збережене представлення зійшлося до однієї версії.

```bash
# List all objects (triggers conversion on read)
kubectl get webapps --all-namespaces -o yaml > /dev/null

# Or use the storage version migrator (kube-storage-version-migrator)
# This systematically reads and rewrites all objects in the new storage version
# (optional component — not installed on default kind/minikube clusters)
```

Зупиніться та спрогнозуйте: якщо у вас є 10 000 ресурсів `WebApp`, збережених як `v1alpha1`, і ви позначаєте `v1beta1` як версію зберігання, чи перепишуться ці об'єкти миттєво в etcd? Ні. API-сервер може обслуговувати конвертовані представлення за запитом, але вам усе одно потрібен процес перезапису або міграції версії зберігання, якщо ви хочете, щоб дані, які лежать в основі, перемістилися до нового представлення зберігання.

Діагностика розбіжності версій починається з виявлення. `kubectl api-resources` показує, які ресурси обслуговуються і яка версія є переважною (preferred), тоді як явний повністю кваліфікований запит ресурсу може показати, що отримує старіший клієнт. Dry-run на стороні сервера так само важливий, бо він виконує встановлення значень за замовчуванням, валідацію та допуск без збереження поганого стану, що робить його найшвидшим способом перевірити зміну схеми CRD, перш ніж ви злиєте її в репозиторій платформи.

### Субресурси та операційні інтерфейси

Субресурси дозволяють вашому власному API поводитися як вбудовані ресурси Kubernetes. Найважливіший із них — `status`, що відокремлює бажаний стан від спостережуваного. Користувачі та інструменти GitOps записують `spec`, щоб описати, чого вони хочуть, тоді як контролери записують `status`, щоб описати, що зараз має кластер. Без такого відокремлення звичайне оновлення основного ресурсу може перезаписати поля статусу, якими володіє контролер, що робить статус менш надійним і може створювати шумні цикли узгодження.

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  subresources:
    status: {}      # Enable /status subresource
  schema:
    openAPIV3Schema:
      # ... schema here
```

З увімкненим субресурсом статусу кінцева точка основного ресурсу ігнорує оновлення `status`, а кінцева точка `/status` ігнорує оновлення `spec`. Звучить просто, але це важлива межа власності. RBAC може надати контролерам дозвіл оновлювати `webapps/status`, не дозволяючи їм переписувати намір користувача, тоді як користувачі можуть оновлювати ресурс, не претендуючи випадково на те, що контролер спостеріг щось, чого він не спостерігав.

```bash
# Users update spec
kubectl patch webapp my-app --type=merge -p '{"spec":{"replicas":5}}'

# Controllers update status (using client-go)
# webapp.Status.ReadyReplicas = 5
# client.Status().Update(ctx, webapp)
```

Субресурс масштабування (scale) — це ще один операційний контракт. Він дозволяє таким інструментам, як `kubectl scale` та Horizontal Pod Autoscaler, взаємодіяти з вашим власним ресурсом через стандартний інтерфейс `scale`, не вивчаючи всю вашу схему. Щоб увімкнути його, ви вказуєте Kubernetes на поле бажаних реплік, поле спостережуваних реплік і, за бажанням, поле селектора міток, що ідентифікує керовані Pod'и.

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  subresources:
    status: {}
    scale:
      specReplicasPath: .spec.replicas
      statusReplicasPath: .status.readyReplicas
      labelSelectorPath: .status.labelSelector
```

Тепер стандартні команди масштабування можуть бути націлені на власний ресурс:

```bash
# Scale the custom resource
kubectl scale webapp my-app --replicas=5

# Use HPA (also requires Metrics Server and a controller that keeps
# status.replicas, status.selector, and readyReplicas current)
kubectl autoscale webapp my-app --min=2 --max=10 --cpu-percent=80
```

Автомасштабування на основі CPU для довільних CRD не є автоматичним лише тому, що існує субресурс масштабування. HPA читає метрики через Metrics Server і записує бажані репліки через кінцеву точку масштабування, але ваш контролер повинен підтримувати поля статусу, які консультує HPA, та відповідно узгоджувати дочірні навантаження.

Зупиніться та спрогнозуйте: якщо ви налаштуєте HPA для свого власного ресурсу, але опустите субресурс `scale`, що зламається першим? У HPA немає стандартної кінцевої точки масштабування, яку можна читати чи записувати для цього ресурсу, тож він не може надійно визначити поточні репліки чи оновити бажані. Виправлення — це не прапорець HPA; це контракт CRD, що розкриває шляхи масштабування з полями, які ваш контролер фактично підтримує.

Стовпці виводу (printer columns) завершують базовий досвід оператора. За замовчуванням `kubectl get` для власного ресурсу показує трохи більше за назву та вік, що змушує користувачів перевіряти YAML для кожного питання. Додаткові стовпці виводу дозволяють API-серверу публікувати корисні фрагменти JSONPath, щоб клієнти могли показувати образ, бажані репліки, готові репліки, фазу, розклад, час останнього бекапу чи інші поля, що мають значення під час звичайного сортування (triage).

```yaml
versions:
- name: v1beta1
  served: true
  storage: true
  additionalPrinterColumns:
  - name: Image
    type: string
    description: "Container image"
    jsonPath: .spec.image
    priority: 0          # 0 = always shown, 1+ = shown with -o wide
  - name: Replicas
    type: integer
    description: "Desired replicas"
    jsonPath: .spec.replicas
  - name: Ready
    type: integer
    description: "Ready replicas"
    jsonPath: .status.readyReplicas
  - name: Status
    type: string
    description: "Current status"
    jsonPath: .status.conditions[?(@.type=="Ready")].status
    priority: 0
  - name: Age
    type: date
    jsonPath: .metadata.creationTimestamp
```

Результат:

```
$ kubectl get webapps
NAME       IMAGE             REPLICAS   READY   STATUS   AGE
my-app     nginx:1.27        3          3       True     5m
frontend   react-app:2.1     2          1       False    2m
```

Хороші стовпці виводу відповідають на перше операційне питання, а не на кожне можливе. Використовуйте пріоритет нуль для стовпців, які потрібні більшості користувачів на вузькому терміналі, і призначайте вищі пріоритети полям, що допомагають у налагодженні, але роблять стандартний вивід надто широким. Якщо стовпець потребує складного JSONPath над масивом, протестуйте його на порожніх, відсутніх та багатоелементних даних, щоб вивід залишався передбачуваним.

| Вираз JSONPath | Вибирає |
|-------------------|---------|
| `.spec.replicas` | Просте поле |
| `.status.conditions[0].status` | Перший елемент масиву |
| `.status.conditions[?(@.type=="Ready")].status` | Фільтр за значенням поля |
| `.metadata.creationTimestamp` | Стандартне поле (використовуйте з `type: date`) |
| `.metadata.labels.app` | Значення мітки |

### CRD WebApp промислового рівня

Наступний CRD зводить частини разом в одне визначення. Він використовує стабільну групу API, ресурс із простором імен, єдину обслуговувану версію зберігання, субресурси статусу та масштабування, стовпці виводу, обмежені поля, мапоподібну семантику списків, значення за замовчуванням та крос-польову валідацію CEL. У згенерованому проєкті оператора цей YAML зазвичай походив би з Go-маркерів та controller-gen, але читання розгорнутого CRD допомагає вам побачити саме те, що отримує API-сервер.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: webapps.apps.kubedojo.io
  annotations:
    controller-gen.kubebuilder.io/version: v0.17.0
spec:
  group: apps.kubedojo.io
  names:
    kind: WebApp
    listKind: WebAppList
    plural: webapps
    singular: webapp
    shortNames:
    - wa
    categories:
    - all
    - kubedojo
  scope: Namespaced
  versions:
  - name: v1beta1
    served: true
    storage: true
    subresources:
      status: {}
      scale:
        specReplicasPath: .spec.replicas
        statusReplicasPath: .status.readyReplicas
    additionalPrinterColumns:
    - name: Image
      type: string
      jsonPath: .spec.image
    - name: Desired
      type: integer
      jsonPath: .spec.replicas
    - name: Ready
      type: integer
      jsonPath: .status.readyReplicas
    - name: Phase
      type: string
      jsonPath: .status.phase
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        description: "WebApp manages a web application deployment with optional ingress."
        required:
        - spec
        properties:
          apiVersion:
            type: string
          kind:
            type: string
          metadata:
            type: object
          spec:
            type: object
            description: "Desired state of the WebApp."
            required:
            - image
            x-kubernetes-validations:
            - rule: "self.minReplicas <= self.maxReplicas"
              message: "minReplicas must not exceed maxReplicas"
            - rule: "self.replicas >= self.minReplicas && self.replicas <= self.maxReplicas"
              message: "replicas must be within [minReplicas, maxReplicas]"
            properties:
              image:
                type: string
                description: "Container image."
                minLength: 1
                maxLength: 255
              replicas:
                type: integer
                description: "Desired number of replicas."
                minimum: 0
                maximum: 500
                default: 2
              minReplicas:
                type: integer
                description: "Minimum replicas for autoscaling."
                minimum: 0
                default: 1
              maxReplicas:
                type: integer
                description: "Maximum replicas for autoscaling."
                minimum: 1
                maximum: 500
                default: 10
              ports:
                type: array
                description: "Ports to expose."
                maxItems: 20
                x-kubernetes-list-type: map
                x-kubernetes-list-map-keys:
                - containerPort
                items:
                  type: object
                  required:
                  - containerPort
                  properties:
                    name:
                      type: string
                      maxLength: 15
                    containerPort:
                      type: integer
                      minimum: 1
                      maximum: 65535
                    protocol:
                      type: string
                      enum: ["TCP", "UDP", "SCTP"]
                      default: "TCP"
              env:
                type: array
                description: "Environment variables."
                maxItems: 100
                items:
                  type: object
                  required:
                  - name
                  properties:
                    name:
                      type: string
                    value:
                      type: string
                    valueFrom:
                      type: object
                      description: "Simplified placeholder — in Kubernetes, valueFrom is an object with secretKeyRef or configMapKeyRef, not a string."
              resources:
                type: object
                properties:
                  requests:
                    type: object
                    properties:
                      cpu:
                        type: string
                        default: "100m"
                      memory:
                        type: string
                        default: "128Mi"
                  limits:
                    type: object
                    properties:
                      cpu:
                        type: string
                        default: "500m"
                      memory:
                        type: string
                        default: "512Mi"
              ingress:
                type: object
                x-kubernetes-validations:
                - rule: "!self.tlsEnabled || self.host != ''"
                  message: "host is required when TLS is enabled"
                properties:
                  enabled:
                    type: boolean
                    default: false
                  host:
                    type: string
                  path:
                    type: string
                    default: "/"
                  tlsEnabled:
                    type: boolean
                    default: false
                  tlsSecretName:
                    type: string
          status:
            type: object
            description: "Observed state of the WebApp."
            properties:
              phase:
                type: string
                enum: ["Pending", "Deploying", "Running", "Degraded", "Failed"]
              readyReplicas:
                type: integer
              availableReplicas:
                type: integer
              observedGeneration:
                type: integer
                format: int64
              conditions:
                type: array
                x-kubernetes-list-type: map
                x-kubernetes-list-map-keys:
                - type
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                      enum: ["True", "False", "Unknown"]
                    reason:
                      type: string
                    message:
                      type: string
                    lastTransitionTime:
                      type: string
                      format: date-time
```

Коли ви тестуєте промисловий CRD, тестуйте і щасливий шлях, і шляхи відхилення. CRD, який приймає лише валідні приклади, усе одно може бути надто дозвільним, а CRD, який відхиляє один невалідний приклад, усе одно може пропустити небезпечний крайовий випадок. Dry-run на стороні сервера є правильним вибором за замовчуванням, бо він вправляє стек валідації API-сервера, не залишаючи по собі ресурсу.

```bash
# Apply the CRD
kubectl apply -f webapp-crd.yaml

# Verify it registered and wait for the API server to serve it
kubectl wait --for=condition=established crd/webapps.apps.kubedojo.io
kubectl api-resources | grep webapp

# Create a valid WebApp
cat << 'EOF' | kubectl apply -f -
apiVersion: apps.kubedojo.io/v1beta1
kind: WebApp
metadata:
  name: my-frontend
  namespace: default
spec:
  image: nginx:1.27
  replicas: 3
  minReplicas: 1
  maxReplicas: 10
  ports:
  - name: http
    containerPort: 80
  - name: metrics
    containerPort: 9090
  env:
  - name: NODE_ENV
    value: production
  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "1"
      memory: "1Gi"
  ingress:
    enabled: true
    host: frontend.example.com
    path: /
    tlsEnabled: true
    tlsSecretName: frontend-tls
EOF

# Check printer columns
kubectl get webapps
kubectl get wa            # shortName works

# Try an invalid resource to diagnose validation failures using server dry-run
cat << 'EOF' | kubectl apply --dry-run=server -f -
apiVersion: apps.kubedojo.io/v1beta1
kind: WebApp
metadata:
  name: invalid-app
spec:
  image: nginx:1.27
  replicas: 3
  minReplicas: 10     # ERROR: minReplicas > maxReplicas (default 10)
  maxReplicas: 5      # ERROR: less than minReplicas
EOF
# Expected: admission error from CEL validation

# Test scale subresource
kubectl scale webapp my-frontend --replicas=5
kubectl get webapp my-frontend -o jsonpath='{.spec.replicas}'
```

Який підхід ви обрали б тут і чому: широку схему, що приймає майже будь-яке поле, аби контролер міг вирішити пізніше, чи суворішу схему, що відхиляє невідомі та некоректні дані одразу? Для платформених API суворіша схема зазвичай дає кращий операційний результат, бо кожен клієнт отримує однаковий контракт, а некоректні дані не дрейфують крізь спостереження (watch), кеші, бекапи та інструменти налагодження. Використовуйте логіку контролера для узгодження та зовнішнього стану, а не для базової валідації форми, яку може примусово виконати допуск.

### Безпечна експлуатація та еволюція CRD

Публікація першої версії CRD зазвичай є легкою частиною; його експлуатація після того, як інші команди починають від нього залежати, — це справжнє випробування. Ставтеся до маніфесту CRD як до артефакту API з тим самим стандартом перевірки, який ви застосували б до HTTP-кінцевої точки чи спільної бібліотеки. Рецензент має запитати, чи кожне обов'язкове поле справді обов'язкове, чи мають необов'язкові поля розумні значення за замовчуванням, чи відповідає семантика злиття списків очікуванням користувачів і чи дає форма статусу контролеру достатньо простору, щоб пояснити частковий прогрес, а не лише успіх або невдачу.

Починайте кожну перевірку CRD з думкою про збережені дані. Щойно об'єкт прийнято, він може бути збережений у etcd, скопійований у бекапи, спостережуваний контролерами, проіндексований клієнтами, експортований інструментами аудиту та закомічений у репозиторії GitOps. Тому розпливчасте поле, що прослизає крізь допуск, може стати частиною операційного запису, навіть якщо контролер пізніше його ігнорує. Сильні схеми — це не марнотратство; вони зменшують кількість некоректного стану, який мусить терпіти кожен інший компонент.

Найбезпечніший патерн перевірки схеми — працювати у зворотному напрямку від поганих прикладів. Напишіть один валідний маніфест, а потім напишіть маніфести, що опускають обов'язкові поля, містять одруківки у важливих полях, перевищують кожен максимум, використовують непідтримувані значення enum, інвертують крос-польові зв'язки та створюють порожні масиви чи мапи там, де контролер очікує вмісту. Запустіть ці маніфести з dry-run на стороні сервера та переконайтеся, що API-сервер повертає корисні повідомлення. Якщо поганий маніфест прийнято, покращіть схему, перш ніж додавати код контролера, що компенсує його.

Встановлення значень за замовчуванням заслуговує на ту саму дисципліну, що й валідація. Значення за замовчуванням — це не просто зручність для користувачів; воно стає збереженою поведінкою API, на яку клієнти можуть навчитися покладатися. Надавайте перевагу значенням за замовчуванням, що є консервативними, недорогими та безпечними, коли користувач новачок у цьому API. Уникайте значень за замовчуванням, що виділяють дорогу інфраструктуру, вмикають публічний доступ чи приховують рішення політики, яке має бути явним у маніфесті, перевіреному командою-власником.

Проєктування статусу CRD має відповідати на три питання для оператора: яке покоління (generation) спостеріг контролер, який condition наразі блокує прогрес і яке поле чи зовнішню залежність слід перевірити далі. Conditions зазвичай довговічніші за один рядок фази, бо вони дозволяють представити кілька істин одночасно, як-от `Ready=False`, `Progressing=True` та `Degraded=True`. Фаза все ще може бути корисною у стовпцях виводу, але conditions дають автоматизації та людям багатшу діагностичну структуру.

Коли ви додаєте conditions, тримайте їх мапоподібними за типом condition, щоб поведінка server-side apply та patch залишалася передбачуваною. Контролер, що замінює весь масив conditions під час кожного узгодження, може боротися з іншими записувачами та ускладнити читання історичних переходів. Контролер, що оновлює один тип condition за раз, включає `observedGeneration` та пише чіткі рядки reason, створює статус, що відчувається рідним для Kubernetes. Схема CRD має підтримувати таку поведінку, обмежуючи значення статусу condition та довжину повідомлень.

Планування версій має починатися перед першим публічним релізом, навіть якщо ви обслуговуєте лише одну версію у перший день. Вирішіть, що вважається сумісним для вашого API: додавання необов'язкових полів, додавання нових значень enum, зміна значень за замовчуванням, посилення валідації та перейменування полів мають різні профілі ризику. Посилення валідації може зламати наявні маніфести, що раніше приймалися, тож воно потребує тієї самої обережності, що й видалення поля. Якщо ви виявите невалідні збережені об'єкти, мігруйте їх перед тим, як робити правило суворішим.

Попередження про застарілість (deprecation warnings) корисні, бо вони зустрічають користувачів там, де ті вже є: усередині запиту до API. Попередження на обслуговуваній версії повідомляє старому скрипту, що він усе ще працює сьогодні, але потребує уваги перед видаленням. Це попередження найцінніше, коли воно поєднане з посібником з міграції, поведінкою конвертації та чіткою датою чи цільовим релізом у документації проєкту. Попередження без шляху міграції лише створює шум, тоді як видалення без попередження створює уникний простій.

Вебхуки конвертації мають бути нудними за задумом. Вони не повинні викликати хмарні API, читати непов'язаний стан кластера чи ухвалювати рішення політики, що змінюються залежно від часу доби. Їхнє завдання — зберігати значення API між версіями, а кожна додаткова залежність розширює радіус ураження (blast radius) читань та записів. Якщо конвертація зазнає збою, клієнти можуть бути неспроможними читати об'єкти у запитуваній версії, тож протестуйте доступність вебхука, конфігурацію TLS та покриття версій перед тим, як робити старіші та новіші версії залежними від нього.

Корисний набір тестів конвертації включає перевірки повного циклу (round-trip). Сконвертуйте старий об'єкт у нову версію, потім сконвертуйте його назад і переконайтеся, що поля, про які дбають старі клієнти, усе ще присутні з тим самим значенням. Сконвертуйте новий об'єкт у стару версію та вирішіть, як нові поля, що не підтримуються, деградують. Іноді ви можете зберегти дані в анотаціях чи статусі під час міграції, але іноді чесна відповідь полягає в тому, що старі версії можуть обслуговувати лише представлення з втратами і їх слід швидко оголосити застарілими.

Міграція зберігання — це операційна подія, а не просто редагування YAML. Після зміни версії зберігання читання може конвертувати об'єкти за запитом, але збережене представлення може залишатися змішаним, доки об'єкти не буде переписано. Це має значення для бекапів, аварійного відновлення, прямої перевірки etcd та продуктивності під час великих операцій переліку (list). Плануйте міграції під час вікна обслуговування, відповідного до кількості об'єктів, і вимірюйте поведінку API-сервера та вебхука під трафіком переліку та спостереження, перш ніж припускати, що зміна дешева.

Server-side apply додає ще одну причину ретельно моделювати семантику списків та мап. Якщо поле представляє іменовані записи, як-от порти, conditions, призначення сповіщень чи політики зберігання, атомарна поведінка списку часто створює зайві конфлікти, бо весь список діє як одне кероване поле. Мапоподібна семантика дозволяє різним менеджерам полів володіти окремими записами, коли ключ стабільний. Ціна в тому, що ви маєте ретельно обрати ключ та валідувати достатньо форми елемента, щоб запобігти неоднозначному володінню.

Стовпці виводу слід переглядати з реальним виводом терміналу, а не лише читаючи YAML. Стовпець, що виглядає розумно в CRD, може погано переноситися на новий рядок, коли назви довгі або повідомлення статусу містять детальні причини. Стандартне представлення має відповідати на перше питання сортування: чи активний ресурс, на яку ціль він впливає, який розклад чи образ налаштовано і чи звітує контролер про прогрес. Ширші діагностичні поля належать за `priority: 1`, щоб користувачі могли вмикати їх за бажанням.

RBAC є частиною контракту CRD, щойно команди починають експлуатувати ресурс. Користувач, що може оновлювати основний ресурс, не повинен автоматично мати змогу оновлювати статус, а контролер, що оновлює статус, не повинен автоматично мати змогу переписувати spec. Так само команда, що може створювати власні ресурси з простором імен, не повинна обов'язково мати змогу модифікувати саме визначення CRD. Відокремте відповідальність cluster-admin за публікацію API від відповідальності орендаря за використання цих API.

Вебхуки допуску та правила CEL доповнюють одне одного, але вирішують різні проблеми. CEL найкращий для локальних детермінованих перевірок над об'єктом, що допускається. Вебхук валідації кращий, коли правило залежить від зовнішнього інвентарю, організаційної політики чи складного парсингу, що зробив би вираз CEL нечитабельним. Вебхук мутації може заповнювати значення, які встановлення значень за замовчуванням CRD не виражає, але кожна мутація має бути достатньо передбачуваною, щоб користувачі не дивувалися, коли читають об'єкт назад.

Спостережуваність для CRD починається з API-сервера і продовжується в контролері. Під час розробки спостерігайте за помилками валідації API-сервера, подіями аудиту, помилками узгодження контролера та переходами статусу разом. Якщо користувачі повідомляють, що об'єкт прийнято, але нічого не сталося, спершу запитайте, чи відповідає об'єкт схемі, чи спостеріг контролер останнє покоління, чи пояснюють conditions статусу блокування і чи розкривають стовпці виводу достатньо стану для швидкої відповіді. Цей шлях розслідування набагато швидший, коли CRD спроєктовано для діагностики від самого початку.

Тестування має включати шляхи оновлення (upgrade) та пониження (downgrade), а не лише чисті встановлення. Застосуйте старий CRD, створіть старі ресурси, оновіть CRD, прочитайте ці ресурси через кожну обслуговувану версію, створіть нові ресурси та переконайтеся, що старіші клієнти отримують або сумісне представлення, або чіткий шлях застарілості. Потім протестуйте очищення та видалення, бо фіналайзери та власні ресурси можуть завадити завершенню видалення CRD. Ці тести виловлюють помилки сумісності, які модульні тести навколо циклів узгодження контролера зазвичай пропускають.

Документація має жити поруч із визначенням CRD, а не лише поруч із контролером. Користувачам потрібно знати, які поля обов'язкові, які значення за замовчуванням застосовуються, які версії застарілі, які conditions статусу мають значення та які стовпці виводу призначені для рутинного сортування. Схема CRD може включати описи, але самі лише описи рідко пояснюють вибір міграції чи операційні очікування. Поєднуйте коментарі схеми з прикладами, що показують валідні ресурси, відхилені ресурси та очікуваний вивід `kubectl get`.

Робочі процеси GitOps роблять сумісність CRD особливо важливою, бо маніфести можуть застосовуватися повторно автоматизацією, що не пам'ятає наради про застарілість. Оновлення контролера може статися швидко, але зміни в репозиторіях багатьох команд часто тривають довше. Обслуговування старої версії з попередженням дає цим репозиторіям час перейти, тоді як конвертація тримає центральне сховище узгодженим під час переходу. Якщо ви видалите версію, перш ніж репозиторії оновляться, збій з'явиться як помилка застосування в кожному конвеєрі, що досі використовує старий API.

Великі кластери також змінюють модель витрат для проєктування CRD. Ресурс, що здається нешкідливим із трьома об'єктами, може бути дорогим із тисячами, особливо якщо статус шумний або необмежені поля роблять кожен об'єкт великим. Кожне оновлення статусу може запускати спостереження, оновлення кешу та подальші узгодження. Обмежуйте розміри повідомлень, уникайте запису статусу, коли нічого не змінилося, і тримайте дані подієподібного типу з високою кардинальністю поза власним ресурсом, якщо вони справді не є частиною бажаного чи спостережуваного стану.

Будьте обережні з полями, що виглядають як аварійні люки (escape hatches). Загальна мапа `config`, збережене невідоме піддерево чи нетипізоване поле `template` можуть бути корисними, коли ви вбудовуєте інший API, але вони також послаблюють валідацію та володіння в server-side apply. Якщо вам потрібна точка розширення, назвіть її чітко, обмежте її розмір та задокументуйте, хто володіє її вмістом. Не використовуйте аварійний люк, щоб уникнути рішення про форму полів, від яких ваш контролер уже залежить.

Семантика видалення теж належить до розмови про API. Багато власних ресурсів використовують фіналайзери, щоб контролер міг прибрати зовнішні ресурси, перш ніж об'єкт зникне. Це означає, що користувачам потрібні conditions статусу та події, що пояснюють прогрес видалення, а схема має включати достатньо полів ідентичності, щоб контролер міг надійно прибирати. Якщо API дозволяє користувачам змінювати ці поля ідентичності після створення, видалення може стати неоднозначним, тож розгляньте правила незмінності для полів, що іменують зовнішні ресурси.

Незмінність полів — один із найкорисніших патернів CEL для CRD, що керують довговічною інфраструктурою. Ціль бекапу, ідентифікатор хмарної бази даних чи storage class можуть бути безпечними для вибору під час створення, але ризикованими для зміни пізніше. Ви можете порівняти `self` та `oldSelf`, щоб відхилити оновлення, що змінило б таке поле, а потім попросити користувачів створити новий ресурс, коли їм потрібна інша ціль. Це робить руйнівні зміни явними, а не приховує їх у звичайному patch.

Нарешті, переглядайте CRD з перспективи людини на чергуванні. Під час інциденту вона спершу читатиме не код вашого контролера; вона запускатиме команди виявлення, перелічуватиме ресурси, перевірятиме статус та шукатиме нещодавні події. Якщо CRD має чіткі стовпці виводу, обмежений та змістовний статус, явні conditions та повідомлення валідації, що вказують на погане поле, сам API допомагає їй рухатися швидко. Якщо CRD — це розпливчастий мішок даних, інженеру на чергуванні доводиться реконструювати намір, поки система вже падає.

Практичне правило просте: робіть невалідні стани непредставними, коли API-сервер має достатньо інформації, щоб їх відхилити. Дозвольте контролеру зосередитися на світі, що змінюється поза об'єктом, як-от Pod'и, що стають готовими, бекапи, що завершуються, сертифікати, що поновлюються, чи хмарні ресурси, що з'являються. CRD, що приймає майже будь-що, змушує контролер бути одночасно і API-сервером, і узгоджувачем. CRD із чіткою схемою, стратегією версій, субресурсами та діагностичними стовпцями дозволяє Kubernetes нести більшу частину контракту API за вас.

---

## Патерни та антипатерни

Патерни проєктування CRD насправді є патернами супроводу API. YAML може виглядати статичним, але ресурс стає частиною робочих процесів користувачів, репозиторіїв Git, скриптів автоматизації, дашбордів, оповіщень та правил RBAC. Вибори проєктування, що здаються незначними під час першої реалізації, стають дорогими, щойно клієнти починають від них залежати, тож використовуйте наведену нижче таблицю як контрольний список перевірки проєктування перед публікацією нової версії.

| Патерн | Коли використовувати | Чому це працює | Міркування щодо масштабування |
|---------|-------------|--------------|-----------------------|
| Структурна схема насамперед | Кожен CRD `apiextensions.k8s.io/v1` | Дає API-серверу достатньо інформації для відсікання, валідації, значень за замовчуванням та server-side apply | Додавайте обмеження до рядків, масивів та мап, щоб об'єкти залишалися в практичних межах |
| Версія перед зміною форми | Будь-який API, який використовують зовнішні клієнти | Дозволяє старим і новим клієнтам співіснувати, поки ви мігруєте маніфести та контролери | Код конвертації слід тестувати як код сумісності, а не як клей |
| Статус і масштабування як контракти | Ресурси, узгоджувані контролерами чи автоскейлерами | Відокремлює намір користувача від спостережуваного стану і дозволяє стандартним інструментам взаємодіяти з ресурсом | RBAC контролера має націлюватися на `/status`, а HPA потребує підтримуваних полів масштабування |
| Стовпці виводу для першого сортування | Ресурси, які користувачі перевіряють під час інцидентів | Робить `kubectl get` корисним, не змушуючи кожного користувача в сирий YAML | Тримайте стандартні стовпці вузькими та переміщуйте вторинні поля за `-o wide` |

Антипатерни зазвичай з'являються, коли команда ставиться до CRD як до внутрішнього формату серіалізації замість публічного API. Ця спокуса зрозуміла, бо CRD легко застосовувати та змінювати, але ця легкість оманлива. Щойно поле існує в живих маніфестах, його зміна чи видалення має ту саму вартість сумісності, що й зміна будь-якого іншого поля API.

| Антипатерн | Що йде не так | Краща альтернатива |
|--------------|-----------------|--------------------|
| Валідація лише в контролері | Некоректний стан досягає etcd та кожного спостерігача, перш ніж контролер відреагує | Відхиляйте помилки форми, діапазону, enum та крос-польові у схемі CRD |
| Довільні об'єкти на кореневому рівні | Невідомі поля обходять контракт і дивують server-side apply | Моделюйте відомі поля явно, зберігаючи невідомі поля лише в іменованих піддеревах розширення |
| Тихе видалення версії | Старіші клієнти раптово зазнають збою, коли обслуговувана версія зникає | Спершу оголосіть застарілою, публікуйте попередження, тримайте конвертацію в робочому стані та мігруйте клієнтів продумано |
| Статус у маніфестах користувачів | Користувачі чи інструменти GitOps перезаписують спостережуваний стан | Увімкніть субресурс статусу та надавайте оновлення статусу лише контролерам |

---

## Фреймворк ухвалення рішень

Використовуйте можливості CRD відповідно до типу проблеми сумісності, яку ви вирішуєте. Найбезпечніший шлях не завжди найскладніший; проста додаткова зміна схеми може не потребувати вебхука, тоді як перейменоване поле зі зміненим значенням майже напевно потребує. Наступна матриця — це практичний спосіб обрати найменший механізм, що все ще зберігає чіткий контракт API.

| Ситуація | Використовуйте це | Уникайте цього | Обґрунтування |
|-----------|----------|------------|-----------|
| Поле обов'язкове для кожного корисного об'єкта | `required` плюс конкретний тип | Помилки контролера після створення | Зворотний зв'язок допуску швидший і запобігає поганому збереженому стану |
| Поле має безпечне поширене значення | `default` у схемі | Patch від мутувального контролера після створення | Значення за замовчуванням стають видимими та узгодженими перед валідацією та зберіганням |
| Два поля мають узгоджуватися | Валідація CEL | Довга гілка узгодження контролера | Крос-польовий допуск тримає невалідні комбінації поза etcd |
| Додається нове необов'язкове поле | Та сама версія чи нова обслуговувана версія, залежно від стабільності | Негайне перемикання версії зберігання | Додаткові зміни не потребують конвертації автоматично |
| Поле перейменовується чи реструктурується | Нова версія плюс вебхук конвертації | Конвертація `None` з несумісними формами | Клієнтам потрібне стабільне значення між запитуваними версіями |
| Операторам потрібен швидкий статус | Стовпці виводу та субресурс статусу | Вимога перевірки сирого YAML | Метадані виявлення мають підтримувати рутинне сортування |
| Автомасштабування має націлюватися на CRD | Субресурс масштабування | Кастомні обхідні шляхи HPA | Стандартні інструменти очікують інтерфейсу масштабування Kubernetes |

Потік реалізації допомагає тримати порядок прямим. Почніть із контракту ресурсу та схеми, потім додайте валідацію для некоректних вхідних даних, потім додайте операційні інтерфейси, і лише тоді ухвалюйте рішення про версіонування для сумісності. Якщо ви почнете з конвертації чи коду контролера, перш ніж схема стане стабільною, ви ризикуєте збудувати складну машинерію навколо контракту, який ще не переглянуто.

---

## Чи знали ви?

1. CRD стали доступними у бета-формі задовго до `apiextensions.k8s.io/v1`, але структурні схеми стали обов'язковими для CRD v1 у Kubernetes 1.16, що перетворило CRD з переважно гнучкого сховища JSON на набагато сильніші контракти API.
2. Kubernetes зберігає власні ресурси в etcd через ту саму машинерію API-сервера, що й вбудовані об'єкти, тож погано обмежений CRD може створювати реальний тиск на зберігання та спостереження, навіть якщо не було написано жодного власного бекенду зберігання.
3. Валідація CEL для CRD дозволяє багатьом крос-польовим перевіркам виконуватися безпосередньо в допуску API-сервера, що уникає розгортання вебхука валідації допуску для простих зв'язків на кшталт `minReplicas <= maxReplicas`.
4. CRD може обслуговувати кілька версій, зберігаючи лише одну, тож версія в маніфесті користувача не обов'язково є представленням, збереженим у etcd.

---

## Типові помилки

| Помилка | Чому це трапляється | Як це виправити |
|---------|----------------|---------------|
| Неструктурна схема | Команди копіюють старі приклади чи залишають вкладені об'єкти нетипізованими | Дайте кожному полю явний тип і тримайте ключові слова валідації всередині типізованих полів |
| Відсутнє `required` для `spec` | Ранні приклади зосереджуються на успішних маніфестах і пропускають тести порожнього об'єкта | Позначте важливі поля як обов'язкові та протестуйте порожні чи часткові ресурси з dry-run на стороні сервера |
| Надто дозвільний regex | Патерн валідує один рядок щасливого шляху, але не крайові випадки | Протестуйте валідні та невалідні приклади, потім поєднайте патерни з обмеженнями мінімальної та максимальної довжини |
| Немає субресурсу статусу | Перший контролер записує статус напряму, і ніхто не помічає проблему власності | Увімкніть `status: {}` та оновлюйте статус через субресурс `/status` |
| Зміна версії зберігання без міграції | Команди очікують, що прапорець зберігання миттєво перепише старі об'єкти | Сплануйте конвертацію та міграцію зберігання, потім перевірте storedVersions та перезаписи об'єктів |
| Використання довільних мап на корені | Гнучкий мішок даних здається швидшим за моделювання API | Тримайте корінь структурним і зберігайте невідомі поля лише в навмисних полях розширення |
| Забуття стовпців виводу | Розробники тестують із `kubectl get -o yaml` замість робочих процесів оператора | Додайте вузькі стандартні стовпці та перемістіть вторинну діагностику за поля пріоритету |
| Надто складні правила CEL | Бізнес-політику переносять у допуск, бо це зручно | Тримайте CEL детермінованим і локальним, а для зовнішньої політики використовуйте вебхуки чи контролери |

---

## Тест

<details>
<summary>1. Ви переглядаєте pull request CRD, що використовує `additionalProperties: true` на корені та опускає явні типи в кількох вкладених об'єктах. CRD зазнає збою на сучасному кластері Kubernetes. Що слід змінити першим і чому?</summary>

Перше виправлення — зробити схему структурною, оголосивши явні типи для кореневого об'єкта та кожного змодельованого вкладеного поля. Довільні властивості на кореневому рівні заважають API-серверу безпечно відсікати, встановлювати значення за замовчуванням та обчислювати керовані поля, тож CRD відхиляється, перш ніж будь-які власні ресурси зможуть його використати. Перемістіть гнучкі мапи в конкретні типізовані поля, якщо API справді потребує розширюваності, і тримайте ключові слова валідації приєднаними до типізованих вузлів схеми. Це безпосередньо перевіряє вміння спроєктувати схему CRD, яку може примусово виконати допуск.

</details>

<details>
<summary>2. У вашої команди є CRD `Database` з полем `status`, але без субресурсу статусу. Розробник застосовує маніфест, що перезаписує `status.activeConnections`, і контролер реагує на хибні дані. Як субресурс статусу змінює режим збою?</summary>

З увімкненим субресурсом статусу оновлення кінцевої точки основного ресурсу ігнорують `status`, тож маніфест користувача не може випадково претендувати на спостережуваний стан. Контролер записує статус через окрему кінцеву точку `/status`, а RBAC може надати цей дозвіл, не надаючи повних оновлень spec. Це тримає бажаний стан та спостережуваний стан під різною власністю, що полегшує міркування про поведінку контролера. Це також узгоджує CRD із конвенціями вбудованих ресурсів Kubernetes.

</details>

<details>
<summary>3. CRD `Certificate` обслуговує `v1alpha1` та `v1beta1`, але `v1alpha1` досі є версією зберігання. Розробник створює об'єкт `v1beta1`. Яке представлення зберігається і що має статися під час читань?</summary>

API-сервер зберігає об'єкт у налаштованій версії зберігання, тож збережене представлення — це `v1alpha1`. Під час запису вхідний об'єкт `v1beta1` конвертується у форму зберігання, перш ніж його буде збережено. Під час читання API-сервер конвертує збережений об'єкт у будь-яку обслуговувану версію, яку запитав клієнт. Якщо версії структурно відрізняються, вебхук конвертації має правильно виконати цей переклад, інакше клієнти побачать збої чи некоректні дані.

</details>

<details>
<summary>4. Користувачі постійно вводять рядки розкладу на кшталт `every day` в CRD `BackupJob`, і контролер відхиляє їх пізніше. Як ви відхиляли б очевидно некоректні розклади перед зберіганням?</summary>

Додайте валідацію схеми до поля `schedule`, щоб API-сервер відхиляв некоректні значення під час допуску. Правило CEL може перевірити, що рядок має п'ять полів, розділених пробілами, тоді як `minLength` та `maxLength` можуть тримати поле обмеженим. Це не доведе, що cron-вираз семантично ідеальний, але блокує поширені некоректні вхідні дані, перш ніж вони досягнуть etcd. Складніша календарна семантика належить до вебхука чи контролера, бо вона потребує глибшого парсингу.

```yaml
x-kubernetes-validations:
- rule: "self.matches('^(\\S+\\s+){4}\\S+$')"
  message: "schedule must be a valid cron expression with 5 fields"
```

</details>

<details>
<summary>5. Два скрипти автоматизації оновлюють різні записи в масиві `ports` CRD, і останній записувач перезаписує запис іншого. Яке розширення схеми допомагає і який ключ ви маєте обрати?</summary>

Використовуйте `x-kubernetes-list-type: map` з `x-kubernetes-list-map-keys`, щоб server-side apply міг керувати окремими записами списку замість того, щоб трактувати весь масив як одне атомарне поле. Ключ має бути стабільним та унікальним для списку, як-от `containerPort` чи `name` порту, залежно від семантики вашого API. Це дозволяє окремим менеджерам полів володіти різними записами, не замінюючи весь список. Проєкт усе одно потребує валідації, щоб запобігти дублікатним чи неоднозначним ключам.

</details>

<details>
<summary>6. Користувач опускає `replicas`, але схема має `default: 2` та правило CEL, що вимагає `replicas >= minReplicas`. Маніфест включає `minReplicas: 1`. Чи проходить валідація і чому?</summary>

Валідація проходить, бо встановлення значень за замовчуванням CRD виконується перед валідацією. API-сервер вставляє `replicas: 2` в об'єкт, а правило CEL оцінюється проти об'єкта зі значенням за замовчуванням, а не проти оригінального розрідженого маніфесту користувача. Збережений ресурс потім містить явне значення за замовчуванням, що робить пізніші читання та поведінку контролера узгодженими. Якби значення за замовчуванням порушувало інше правило, запит зазнав би збою після встановлення значень за замовчуванням.

</details>

<details>
<summary>7. Оператори кажуть, що `kubectl get backuppolicies` переноситься на новий рядок на малих терміналах, але їм усе одно іноді потрібні детальні діагностичні поля. Як слід налаштувати стовпці виводу?</summary>

Тримайте лише суттєві поля на пріоритеті нуль, бо ці стовпці показуються у звичайному виводі `kubectl get`. Перемістіть вторинні поля, як-от детальні рядки reason, кількість бекапів чи позначки часу, на пріоритет один чи вищий, щоб вони з'являлися з `-o wide`. Це дає рутинному сортуванню компактне стандартне представлення, зберігаючи деталі для досвідчених користувачів. Протестуйте JSONPath на відсутні поля статусу, щоб нові об'єкти не давали заплутаного виводу.

</details>

<details>
<summary>8. Розробник пише `imgae` замість `image` у суворому маніфесті власного ресурсу, що опускає обов'язкове поле `image`. Що станеться?</summary>

Застосування зазнає збою валідації, бо `spec.image` обов'язкове. Якби схема не позначала `image` як обов'язкове, а маніфест містив лише поле з одруківкою `imgae`, API-сервер відсік би це невідоме поле під час допуску, бо CRD має структурну схему, що не включає `imgae`. Відсікання видаляє поля поза оголошеною схемою перед збереженням, що тримає збережені об'єкти узгодженими з контрактом API. Виправлення — вимагати важливі поля та використовувати тести dry-run на стороні сервера, що включають поширені одруківки та пропуски.

</details>

---

## Практична вправа

Сценарій вправи: ви публікуєте API `BackupPolicy` для прикладних команд, яким потрібні заплановані бекапи для навантажень та персистентних даних. API починається з простої форми `v1alpha1` і еволюціонує в багатшу форму `v1beta1` зі структурованим зберіганням, селекторами цілей, сповіщеннями, статусом та стовпцями виводу. Ваша мета — не побудувати контролер бекапів зараз; ваша мета — зробити контракт API Kubernetes достатньо сильним, щоб майбутній контролер отримував валідні, обмежені та виявлювані об'єкти.

### Завдання 1: Створіть CRD

Застосуйте CRD, що обслуговує обидві версії, позначає `v1beta1` як зберігання, оголошує `v1alpha1` застарілою, вмикає статус та публікує корисні стовпці виводу. Оскільки `v1alpha1` та `v1beta1` використовують різні схеми, а цей CRD не має блока `spec.conversion`, стратегія за замовчуванням `None` лише перепозначає `apiVersion` — крос-версійні читання повертають збережені поля без перекладу. У промисловому середовищі ви додали б `spec.conversion.strategy: Webhook` або тримали б схеми версій сумісними. Прочитайте маніфест перед запуском і визначте, яке правило валідації не дає `retention.maxCount` бути меншим за `retention.minCount`.

```bash
cat << 'CRDEOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backuppolicies.data.kubedojo.io
spec:
  group: data.kubedojo.io
  names:
    kind: BackupPolicy
    listKind: BackupPolicyList
    plural: backuppolicies
    singular: backuppolicy
    shortNames:
    - bp
    categories:
    - kubedojo
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: false
    deprecated: true
    deprecationWarning: "data.kubedojo.io/v1alpha1 BackupPolicy is deprecated; use v1beta1"
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required:
            - schedule
            - target
            properties:
              schedule:
                type: string
              retentionDays:
                type: integer
                minimum: 1
                maximum: 365
                default: 30
              target:
                type: string
          status:
            type: object
            properties:
              lastBackup:
                type: string
                format: date-time
              backupCount:
                type: integer
    additionalPrinterColumns:
    - name: Schedule
      type: string
      jsonPath: .spec.schedule
    - name: Retention
      type: integer
      jsonPath: .spec.retentionDays
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp

  - name: v1beta1
    served: true
    storage: true
    subresources:
      status: {}
    additionalPrinterColumns:
    - name: Schedule
      type: string
      jsonPath: .spec.schedule
    - name: Retention
      type: string
      jsonPath: .spec.retention.maxAge
    - name: Last Backup
      type: string
      jsonPath: .status.lastBackupTime
    - name: Status
      type: string
      jsonPath: .status.phase
    - name: Backups
      type: integer
      jsonPath: .status.successfulBackups
      priority: 1
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
    schema:
      openAPIV3Schema:
        type: object
        required:
        - spec
        properties:
          spec:
            type: object
            required:
            - schedule
            - target
            x-kubernetes-validations:
            - rule: "self.retention.maxCount >= self.retention.minCount"
              message: "maxCount must be >= minCount"
            properties:
              schedule:
                type: string
                description: "Cron schedule expression."
                minLength: 9
                maxLength: 100
              paused:
                type: boolean
                default: false
              retention:
                type: object
                properties:
                  maxAge:
                    type: string
                    description: "Maximum age (e.g., 30d, 12h)."
                    pattern: '^[0-9]+(d|h|m)$'
                    default: "30d"
                  maxCount:
                    type: integer
                    minimum: 1
                    maximum: 1000
                    default: 100
                  minCount:
                    type: integer
                    minimum: 1
                    maximum: 100
                    default: 3
              target:
                type: object
                required:
                - kind
                properties:
                  kind:
                    type: string
                    enum: ["Deployment", "StatefulSet", "PersistentVolumeClaim", "Namespace"]
                  name:
                    type: string
                  labelSelector:
                    type: object
                    properties:
                      matchLabels:
                        type: object
                        additionalProperties:
                          type: string
              notifications:
                type: array
                maxItems: 5
                items:
                  type: object
                  required:
                  - type
                  - endpoint
                  properties:
                    type:
                      type: string
                      enum: ["slack", "email", "webhook"]
                    endpoint:
                      type: string
                    onlyOnFailure:
                      type: boolean
                      default: true
          status:
            type: object
            properties:
              phase:
                type: string
                enum: ["Active", "Paused", "Failing", "Unknown"]
              lastBackupTime:
                type: string
                format: date-time
              nextBackupTime:
                type: string
                format: date-time
              successfulBackups:
                type: integer
              failedBackups:
                type: integer
              conditions:
                type: array
                items:
                  type: object
                  required:
                  - type
                  - status
                  properties:
                    type:
                      type: string
                    status:
                      type: string
                      enum: ["True", "False", "Unknown"]
                    reason:
                      type: string
                    message:
                      type: string
                    lastTransitionTime:
                      type: string
                      format: date-time
CRDEOF
```

<details>
<summary>Нотатки до розв'язку</summary>

Крос-польове правило приєднано до `spec` у схемі `v1beta1` і порівнює `self.retention.maxCount` з `self.retention.minCount`. Якщо CRD застосовується успішно, Kubernetes прийняв структурну схему та зареєстрував шлях ресурсу. Якщо застосування зазнає збою, спершу перевірте помилку валідації, а не змінюйте контролер, бо контролер не задіяний у реєстрації CRD.

</details>

```bash
# Wait for the CRD to become established before using it
kubectl wait --for=condition=established crd/backuppolicies.data.kubedojo.io
```

### Завдання 2: Створіть валідну BackupPolicy

Створіть ресурс `v1beta1`, що вправляє поля розкладу, зберігання, цілі та сповіщень. Кінцева точка Slack використовує навчальне значення, що явно не є реальними обліковими даними, бо приклади мають навчати структури, не навчаючи слухачів вставляти секрети в репозиторії.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: daily-db-backup
  namespace: default
spec:
  schedule: "0 2 * * *"
  retention:
    maxAge: "30d"
    maxCount: 90
    minCount: 7
  target:
    kind: StatefulSet
    name: postgres
  notifications:
  - type: slack
    endpoint: "https://hooks.slack.com/services/YOUR/WEBHOOK/HERE"
    onlyOnFailure: true
EOF
```

<details>
<summary>Нотатки до розв'язку</summary>

Цей об'єкт має бути прийнято, бо він включає обидва обов'язкові поля `spec`, задовольняє зв'язок зберігання та використовує об'єкт сповіщення з обов'язковими `type` та `endpoint`. Після створення прочитайте об'єкт назад і зверніть увагу, що значення за замовчуванням, як-от `paused`, можуть з'явитися, навіть якщо ви їх не надавали. Це підтверджує, що встановлення значень за замовчуванням відбулося перед зберіганням.

</details>

### Завдання 3: Перевірте виявлення та стовпці виводу

Використовуйте виявлення та звичайний вивід `kubectl get`, щоб підтвердити, що API придатне для використання людьми та автоматизацією. Коротка назва зручна в інтерактивному режимі, але повна команда залишається читабельною у скриптах та прикладах модуля.

```bash
kubectl get backuppolicies
kubectl get bp              # shortName
kubectl get bp -o wide      # includes priority 1 columns
```

<details>
<summary>Нотатки до розв'язку</summary>

Стандартний вивід має включати стовпці розкладу, зберігання, останнього бекапу, статусу та віку. Оскільки в цій вправі жоден контролер не оновлює статус, деякі стовпці статусу можуть бути порожніми, і це очікувано. Вивід `-o wide` має включати стовпець кількості бекапів пріоритету один, що демонструє, як пріоритет стовпця виводу керує стандартною шириною.

</details>

### Завдання 4: Протестуйте збої валідації

Надішліть невалідні ресурси з видимим зворотним зв'язком сервера. Ці приклади навмисно використовують `|| true`, щоб сесія оболонки могла продовжитися після очікуваного збою, але не інтерпретуйте продовжену оболонку як успішний запит до Kubernetes.

```bash
# Missing required field
cat << 'EOF' | kubectl apply -f - 2>&1 || true
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: bad-policy-1
spec:
  schedule: "0 2 * * *"
EOF

# Invalid retention (minCount > maxCount)
cat << 'EOF' | kubectl apply -f - 2>&1 || true
apiVersion: data.kubedojo.io/v1beta1
kind: BackupPolicy
metadata:
  name: bad-policy-2
spec:
  schedule: "0 2 * * *"
  retention:
    maxCount: 2
    minCount: 10
  target:
    kind: Deployment
    name: my-app
EOF
```

<details>
<summary>Нотатки до розв'язку</summary>

Перший запит має зазнати збою, бо `target` обов'язкове, а другий має зазнати збою, бо правило CEL відхиляє зв'язок зберігання. Обидва збої відбуваються під час допуску, перш ніж об'єкти буде збережено. Якщо невалідний об'єкт з'являється в `kubectl get backuppolicies`, перегляньте розташування правила у схемі та переконайтеся, що ви застосували останнє визначення CRD.

</details>

### Завдання 5: Протестуйте застарілу версію

Створіть об'єкт через застарілу версію, щоб спостерегти попередження про застарілість та закріпити різницю між обслуговуваними версіями та версією зберігання. Це той тип мосту сумісності, який ви використовуєте під час міграції старих маніфестів.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: data.kubedojo.io/v1alpha1
kind: BackupPolicy
metadata:
  name: old-style-backup
spec:
  schedule: "0 3 * * 0"
  retentionDays: 14
  target: "deployment/web"
EOF
# You should see a deprecation warning
```

<details>
<summary>Нотатки до розв'язку</summary>

Запит усе одно має успішно виконатися, бо `v1alpha1` обслуговується, але попередження повідомляє користувачам, яку версію прийняти. Оскільки `v1beta1` є версією зберігання, а дві версії мають різні форми зі стандартною конвертацією `None`, читання об'єкта як `v1beta1` повертає збережені поля `v1alpha1` без перекладу `target: "deployment/web"` у структурований об'єкт цілі `v1beta1`. Ця вправа зосереджена на поверхні CRD, тож сприймайте попередження як підказку спланувати вебхук конвертації перед реальною міграцією.

</details>

### Завдання 6: Очищення

Видаліть ресурси та CRD, коли закінчите. Видалення CRD видаляє кінцеву точку власного ресурсу та збережені власні ресурси, тож запускайте очищення лише в одноразовому навчальному кластері.

```bash
kubectl delete backuppolicies --all
kubectl delete crd backuppolicies.data.kubedojo.io
```

<details>
<summary>Нотатки до розв'язку</summary>

Після очищення `kubectl api-resources | grep backuppolicies` більше не має показувати ресурс. Якщо ресурси залишаються, перевірте простори імен та фіналайзери, перш ніж припускати, що видалення CRD зазнало збою. Реальний оператор може додавати фіналайзери до власних ресурсів, що може затримати видалення, доки логіка очищення не завершиться.

</details>

**Критерії успіху**:

- [ ] CRD успішно реєструється з обома версіями.
- [ ] Валідні ресурси створюються без помилок.
- [ ] Невалідні ресурси відхиляються з чіткими повідомленнями про помилки.
- [ ] Крос-польова валідація CEL працює для `minCount <= maxCount`.
- [ ] Стовпці виводу коректно відображаються у стандартному та широкому виводі.
- [ ] Коротка назва `bp` працює для інтерактивного виявлення.
- [ ] `v1alpha1` показує попередження про застарілість.
- [ ] Субресурс статусу увімкнено, коли ви перевіряєте CRD.

---

## Джерела

- https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
- https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/
- https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definition-versioning/
- https://kubernetes.io/docs/reference/kubernetes-api/extend-resources/custom-resource-definition-v1/
- https://kubernetes.io/docs/reference/using-api/api-concepts/
- https://kubernetes.io/docs/reference/using-api/deprecation-policy/
- https://kubernetes.io/docs/reference/using-api/cel/
- https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
- https://kubernetes.io/docs/reference/using-api/server-side-apply/
- https://kubernetes.io/docs/tasks/manage-kubernetes-objects/update-api-object-kubectl-patch/
- https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- https://kubernetes.io/docs/reference/kubectl/jsonpath/

## Наступний модуль

[Модуль 1.3: Побудова контролерів за допомогою client-go](../module-1.3-controllers-client-go/) — напишіть повноцінний контролер Kubernetes з нуля, використовуючи патерни проєктування API, які ви відпрацювали в Модулях 1.1 та 1.2.









